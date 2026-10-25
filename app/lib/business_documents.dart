import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'business_documentation.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;

const businessDocumentKinds = {
  'offer': 'Angebot',
  'estimate': 'Kostenvoranschlag',
  'order_confirmation': 'Auftragsbestätigung',
  'delivery_note': 'Lieferschein',
  'invoice': 'Rechnung',
  'advance_invoice': 'Abschlagsrechnung',
  'cumulative_invoice': 'Kumulierte Rechnung',
  'final_invoice': 'Schlussrechnung',
  'cancellation': 'Storno',
};
const businessPositionKinds = {
  'labor': 'Lohn',
  'material': 'Material',
  'service': 'Leistung',
  'machine': 'Maschine',
};
const businessDocumentStates = {
  'draft': 'Entwurf',
  'final': 'Festgeschrieben',
  'finalized': 'Festgeschrieben',
  'signed': 'Unterschrieben',
  'cancelled': 'Storniert',
};

class BusinessDocumentsPage extends StatelessWidget {
  const BusinessDocumentsPage({super.key, required this.session});
  final BusinessSession session;
  @override
  Widget build(BuildContext context) => BusinessCollection(
    session: session,
    path: '/documents',
    title: 'Belege',
    readPermission: 'finance.read',
    writePermission: 'finance.write',
    fields: const [],
    createLabel: 'Beleg erstellen',
    titleOf: (r) =>
        '${r['title'] ?? businessDocumentKinds[r['kind']] ?? 'Beleg'}',
    subtitleOf: (r) =>
        '${businessDocumentKinds[r['kind']] ?? 'Beleg'} · ${r['number'] ?? 'Ohne Ausgabenummer'} · ${businessDocumentStates[r['status']] ?? r['status']}',
    onCreate: () async {
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => BusinessDocumentEditor(session: session),
        ),
      );
    },
    onOpen: (r) async {
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => BusinessDocumentPage(session: session, id: r['id']),
        ),
      );
    },
  );
}

class BusinessDocumentEditor extends StatefulWidget {
  const BusinessDocumentEditor({
    super.key,
    required this.session,
    this.document,
    this.templateMode = false,
  });
  final BusinessSession session;
  final Map<String, dynamic>? document;
  final bool templateMode;
  @override
  State<BusinessDocumentEditor> createState() => _BusinessDocumentEditorState();
}

class _BusinessDocumentEditorState extends State<BusinessDocumentEditor> {
  final form = GlobalKey<FormState>();
  late final TextEditingController title, notes, issue, due, buyerReference;
  final templateName = TextEditingController(), intro = TextEditingController();
  bool get canEdit => widget.templateMode
      ? widget.session.canWrite('settings.manage')
      : widget.session.canWrite('finance.write');
  final buyerFields = <String, TextEditingController>{};
  final hourlyRate = TextEditingController(),
      timeTax = TextEditingController(text: '19');
  List<Map<String, dynamic>> timeSources = [],
      priorDocuments = [],
      templates = [];
  final selectedTimeIds = <String>{}, previousIds = <String>{};
  String? inputError, selectedTemplateId;
  int? selectedTemplateRevision;
  late String kind;
  String? project;
  late List<Map<String, dynamic>> positions;
  bool busy = false, uncertain = false;
  String? error;
  final key = 'document-editor-${DateTime.now().microsecondsSinceEpoch}';
  Map<String, dynamic>? frozen;
  @override
  void initState() {
    super.initState();
    final d = widget.document ?? {};
    templateName.text = d['name'] ?? '';
    intro.text = d['intro'] ?? '';
    title = TextEditingController(text: d['title'] ?? '');
    notes = TextEditingController(text: d['notes'] ?? '');
    issue = TextEditingController(
      text:
          d['issue_date'] ?? DateTime.now().toIso8601String().substring(0, 10),
    );
    due = TextEditingController(text: d['due_date'] ?? '');
    buyerReference = TextEditingController(text: d['buyer_reference'] ?? '');
    final buyer = businessMap(d['buyer']);
    for (final name in [
      'name',
      'address_line',
      'postal_code',
      'city',
      'country',
      'email',
      'endpoint_id',
      'endpoint_scheme',
    ])
      buyerFields[name] = TextEditingController(
        text: buyer[name] ?? (name == 'country' ? 'DE' : ''),
      );
    kind = d['kind'] ?? 'offer';
    project = d['project_id'] ?? widget.session.projectId;
    positions = (d['positions'] as List? ?? []).map(businessMap).toList();
    previousIds.addAll(
      List<String>.from(d['previous_document_ids'] as List? ?? []),
    );
    widget.session.addListener(changed);
    if (!widget.templateMode) loadInputs();
  }

  Future<void> loadInputs() async {
    final current = project;
    if (current == null || !widget.session.can('finance.read')) return;
    try {
      final results = await Future.wait([
        widget.session.read(
          '/documents/time-sources?${Uri(queryParameters: {'project_id': current}).query}',
        ),
        widget.session.read(
          '/documents?${Uri(queryParameters: {'project_id': current}).query}',
        ),
        widget.session.read('/templates'),
      ]);
      if (!mounted || !widget.session.allowed || project != current) return;
      setState(() {
        timeSources = businessItems(results[0]);
        priorDocuments = businessItems(results[1])
            .where(
              (d) =>
                  d['status'] == 'final' &&
                  d['id'] != widget.document?['id'] &&
                  '${d['kind']}'.contains('invoice'),
            )
            .toList();
        templates = businessItems(results[2]);
      });
    } catch (_) {
      if (mounted && project == current)
        setState(
          () => inputError = 'Vorlagen, Vorbelege oder freigegebene Zeiten konnten nicht geladen werden. Manuelle Positionen bleiben möglich.',
        );
    }
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    for (final c in [title, notes, issue, due, buyerReference]) {
      c.clear();
      c.dispose();
    }
    templateName.clear();
    templateName.dispose();
    intro.clear();
    intro.dispose();
    hourlyRate.clear();
    hourlyRate.dispose();
    timeTax.clear();
    timeTax.dispose();
    for (final c in buyerFields.values) {
      c.clear();
      c.dispose();
    }
    super.dispose();
  }

  Future<void> position([int? index]) async {
    if (index != null && positions[index]['source_type'] == 'time') return;
    final initial = index == null
        ? <String, dynamic>{
            'quantity': '1',
            'unit': 'C62',
            'unit_price_net': '0',
            'tax_rate': '19',
            'kind': 'service',
          }
        : positions[index];
    await showDialog<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: index == null ? 'Position hinzufügen' : 'Position bearbeiten',
        initial: initial,
        fields: const [
          BusinessField(
            'description',
            'Beschreibung',
            type: BusinessInput.multiline,
            required: true,
          ),
          BusinessField(
            'quantity',
            'Menge',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'unit',
            'Einheit',
            required: true,
            hint: 'C62 = Stück · HUR = Stunde · MTR = Meter',
          ),
          BusinessField(
            'unit_price_net',
            'Einzelpreis netto (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'tax_rate',
            'Umsatzsteuer (%)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'kind',
            'Kostenart',
            type: BusinessInput.choice,
            required: true,
            choices: businessPositionKinds,
          ),
        ],
        onSave: (values) async {
          if (!mounted) return;
          setState(() {
            if (index == null)
              positions.add(values);
            else
              positions[index] = values;
          });
        },
      ),
    );
  }

  Future<void> save() async {
    if (busy || !canEdit || !(form.currentState?.validate() ?? false)) return;
    if ((!widget.templateMode && project == null) ||
        (positions.isEmpty && selectedTimeIds.isEmpty)) {
      setState(
        () => error = 'Bitte wählen Sie ein Projekt und erfassen Sie mindestens eine Position.',
      );
      return;
    }
    if (widget.templateMode && templateName.text.trim().isEmpty) {
      setState(() => error = 'Bitte den Vorlagennamen eingeben.');
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (widget.templateMode) {
        frozen ??= {
          'name': templateName.text.trim(),
          'kind': kind,
          'title': title.text.trim(),
          'intro': intro.text,
          'notes': notes.text,
          'positions': positions,
          if (widget.document != null) 'revision': widget.document!['revision'],
        };
      }
      frozen ??= {
        'project_id': project,
        'kind': kind,
        'title': title.text.trim(),
        'issue_date': issue.text.trim(),
        if (due.text.trim().isNotEmpty) 'due_date': due.text.trim(),
        'buyer_reference': buyerReference.text.trim(),
        if (buyerFields['name']!.text.trim().isNotEmpty)
          'buyer': {
            for (final entry in buyerFields.entries)
              entry.key: entry.value.text.trim(),
          },
        'notes': notes.text.trim(),
        'intro': intro.text,
        'positions': positions
            .where(
              (p) =>
                  p['source_type'] != 'time' ||
                  !selectedTimeIds.contains(p['source_id']),
            )
            .toList(),
        'previous_document_ids': previousIds.toList(),
        if (selectedTemplateId != null) 'template_id': selectedTemplateId,
        if (selectedTemplateId != null)
          'template_revision': selectedTemplateRevision,
        if (selectedTimeIds.isNotEmpty)
          'time_entry_ids': selectedTimeIds.toList(),
        if (selectedTimeIds.isNotEmpty)
          'hourly_rate_net': businessDecimal(hourlyRate.text),
        if (selectedTimeIds.isNotEmpty)
          'time_tax_rate': businessDecimal(timeTax.text),
        if (widget.document != null) 'revision': widget.document!['revision'],
      };
      final result = businessMap(
        await widget.session.command(
          key,
          '${widget.templateMode ? '/templates' : '/documents'}${widget.document == null ? '' : '/${widget.document!['id']}'}',
          frozen!,
        ),
      );
      if (mounted && widget.session.allowed && widget.templateMode) {
        Navigator.pop(context);
        return;
      }
      if (mounted && widget.session.allowed)
        Navigator.pushReplacement<void, void>(
          context,
          MaterialPageRoute(
            builder: (_) =>
                BusinessDocumentPage(session: widget.session, id: result['id']),
          ),
        );
    } on ApiException catch (e) {
      if (mounted)
        setState(() {
          error = e.message;
          uncertain = e.status == 0 || e.status >= 500 || e.status == 429;
          if (!uncertain) frozen = null;
        });
    } on FormatException catch (e) {
      if (mounted)
        setState(() {
          error = e.message;
          frozen = null;
        });
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final enabled = !busy && !uncertain && canEdit;
    final choices = {
      for (final e in businessDocumentKinds.entries)
        if (widget.templateMode ||
            !e.key.contains('invoice') ||
            widget.session.canWrite('finance.write'))
          e.key: e.value,
    };
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.templateMode
              ? 'Dokumentvorlage'
              : widget.document == null
              ? 'Beleg erstellen'
              : 'Entwurf bearbeiten',
        ),
      ),
      body: !widget.session.can('finance.read')
          ? const Center(child: Text('Der Zugang ist nicht mehr verfügbar.'))
          : ListView(
              padding: const EdgeInsets.all(24),
              children: [
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 900),
                  child: Form(
                    key: form,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Notice(
                          'Der Entwurf erhält erst bei der ausdrücklichen Festschreibung eine Ausgabenummer. Preise und Steuern berechnet der Server.',
                        ),
                        if (error != null) Notice(error!, error: true),
                        const SizedBox(height: 16),
                        if (widget.session.projectId == null &&
                            !widget.templateMode)
                          DropdownButtonFormField<String>(
                            initialValue: project,
                            isExpanded: true,
                            decoration: const InputDecoration(
                              labelText: 'Projekt',
                            ),
                            items: [
                              for (final p in widget.session.projects)
                                DropdownMenuItem(
                                  value: p['id'] as String,
                                  child: Text('${p['name']}'),
                                ),
                            ],
                            onChanged: enabled && widget.document == null
                                ? (v) {
                                    setState(() {
                                      project = v;
                                      selectedTimeIds.clear();
                                      previousIds.clear();
                                    });
                                    loadInputs();
                                  }
                                : null,
                            validator: (v) =>
                                v == null ? 'Bitte Projekt wählen.' : null,
                          ),
                        const SizedBox(height: 12),
                        if (widget.templateMode) ...[
                          TextFormField(
                            controller: templateName,
                            enabled: enabled,
                            decoration: const InputDecoration(
                              labelText: 'Vorlagenname',
                            ),
                            validator: (value) => (value ?? '').trim().isEmpty
                                ? 'Bitte Vorlagenname eingeben.'
                                : null,
                          ),
                          const SizedBox(height: 12),
                        ],
                        DropdownButtonFormField<String>(
                          initialValue: kind,
                          decoration: const InputDecoration(
                            labelText: 'Belegart',
                          ),
                          items: [
                            for (final e in choices.entries)
                              DropdownMenuItem(
                                value: e.key,
                                child: Text(e.value),
                              ),
                          ],
                          onChanged: enabled
                              ? (v) => setState(() => kind = v!)
                              : null,
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          key: const ValueKey('business-document-title'),
                          controller: title,
                          enabled: enabled,
                          decoration: const InputDecoration(labelText: 'Titel'),
                          validator: (v) => (v ?? '').trim().isEmpty
                              ? 'Bitte Titel eingeben.'
                              : null,
                        ),
                        const SizedBox(height: 12),
                        if (!widget.templateMode)
                          TextFormField(
                            controller: issue,
                            enabled: enabled,
                            decoration: const InputDecoration(
                              labelText: 'Belegdatum (JJJJ-MM-TT)',
                            ),
                            validator: (v) => DateTime.tryParse(v ?? '') == null
                                ? 'Bitte gültiges Datum eingeben.'
                                : null,
                          ),
                        const SizedBox(height: 12),
                        if (!widget.templateMode)
                          TextFormField(
                            controller: due,
                            enabled: enabled,
                            decoration: const InputDecoration(
                              labelText: 'Zahlungsziel (JJJJ-MM-TT, optional)',
                            ),
                            validator: (v) =>
                                (v ?? '').isNotEmpty &&
                                    DateTime.tryParse(v!) == null
                                ? 'Bitte gültiges Datum eingeben.'
                                : null,
                          ),
                        const SizedBox(height: 12),
                        if (!widget.templateMode)
                          TextFormField(
                            controller: buyerReference,
                            enabled: enabled,
                            decoration: const InputDecoration(
                              labelText:
                                  'Leitweg-ID / Käuferreferenz (optional)',
                            ),
                          ),
                        const SizedBox(height: 12),
                        if (!widget.templateMode)
                          ExpansionTile(
                            title: const Text(
                              'Empfänger und Rechnungsanschrift',
                            ),
                            subtitle: const Text(
                              'Diese Daten werden mit der Belegfassung eingefroren.',
                            ),
                            tilePadding: EdgeInsets.zero,
                            children: [
                              for (final field in const {
                                'name': 'Name / Firma',
                                'address_line': 'Straße und Hausnummer',
                                'postal_code': 'Postleitzahl',
                                'city': 'Ort',
                                'country': 'Ländercode',
                                'email': 'E-Mail für den Versand',
                                'endpoint_id':
                                    'E-Rechnungsempfänger-ID (optional)',
                                'endpoint_scheme':
                                    'Empfänger-ID-Schema (optional)',
                              }.entries)
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 12),
                                  child: TextFormField(
                                    controller: buyerFields[field.key],
                                    enabled: enabled,
                                    decoration: InputDecoration(
                                      labelText: field.value,
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        TextFormField(
                          controller: intro,
                          enabled: enabled,
                          maxLines: 3,
                          decoration: const InputDecoration(
                            labelText: 'Einleitung / Textbaustein',
                          ),
                        ),
                        TextFormField(
                          controller: notes,
                          enabled: enabled,
                          maxLines: 3,
                          decoration: const InputDecoration(
                            labelText: 'Hinweise',
                          ),
                        ),
                        const SizedBox(height: 24),
                        if (inputError != null) Notice(inputError!),
                        if (!widget.templateMode &&
                            templates.isNotEmpty &&
                            widget.document == null)
                          ExpansionTile(
                            tilePadding: EdgeInsets.zero,
                            title: const Text('Aus einer Vorlage starten'),
                            children: [
                              for (final template in templates)
                                ListTile(
                                  title: Text('${template['name']}'),
                                  onTap: !enabled
                                      ? null
                                      : () async {
                                          if (positions.isNotEmpty &&
                                              !await businessConfirm(
                                                context,
                                                title: 'Vorlage übernehmen?',
                                                message: 'Die bisherigen Positionen werden durch die gewählte Vorlage ersetzt.',
                                                action: 'Vorlage übernehmen',
                                              ))
                                            return;
                                          if (!mounted || !enabled) return;
                                          setState(() {
                                            selectedTemplateId = template['id'];
                                            selectedTemplateRevision =
                                                template['revision'];
                                            title.text =
                                                template['title'] ?? '';
                                            notes.text =
                                                template['notes'] ?? '';
                                            kind = template['kind'] ?? kind;
                                            positions =
                                                (template['positions']
                                                            as List? ??
                                                        [])
                                                    .map(businessMap)
                                                    .toList();
                                          });
                                        },
                                ),
                            ],
                          ),
                        if (!widget.templateMode && timeSources.isNotEmpty)
                          ExpansionTile(
                            tilePadding: EdgeInsets.zero,
                            title: const Text(
                              'Freigegebene Arbeitszeiten übernehmen',
                            ),
                            subtitle: const Text(
                              'Die Zuordnung schützt vor doppelter Abrechnung.',
                            ),
                            children: [
                              for (final time in timeSources)
                                CheckboxListTile(
                                  contentPadding: EdgeInsets.zero,
                                  title: Text(
                                    '${businessDate(time['work_date'] ?? time['date'])} · ${time['net_seconds']} Sekunden',
                                  ),
                                  value: selectedTimeIds.contains(
                                    time['entry_id'],
                                  ),
                                  onChanged: enabled
                                      ? (checked) => setState(() {
                                          checked == true
                                              ? selectedTimeIds.add(
                                                  time['entry_id'],
                                                )
                                              : selectedTimeIds.remove(
                                                  time['entry_id'],
                                                );
                                        })
                                      : null,
                                ),
                              TextFormField(
                                controller: hourlyRate,
                                enabled: enabled,
                                decoration: const InputDecoration(
                                  labelText:
                                      'Abrechnungssatz netto je Stunde (€)',
                                ),
                                validator: (value) {
                                  if (selectedTimeIds.isEmpty) return null;
                                  try {
                                    businessDecimal(value ?? '');
                                    return null;
                                  } catch (_) {
                                    return 'Bitte den Stundensatz eingeben.';
                                  }
                                },
                              ),
                              const SizedBox(height: 12),
                              TextFormField(
                                controller: timeTax,
                                enabled: enabled,
                                decoration: const InputDecoration(
                                  labelText:
                                      'Umsatzsteuer für übernommene Zeiten (%)',
                                ),
                              ),
                            ],
                          ),
                        if ([
                          'cumulative_invoice',
                          'final_invoice',
                        ].contains(kind))
                          ExpansionTile(
                            tilePadding: EdgeInsets.zero,
                            title: const Text(
                              'Bereits ausgestellte Rechnungen berücksichtigen',
                            ),
                            children: [
                              if (priorDocuments.isEmpty)
                                const Padding(
                                  padding: EdgeInsets.all(12),
                                  child: Text(
                                    'Keine freigegebenen Vorbelege in diesem Projekt verfügbar.',
                                  ),
                                ),
                              for (final previous in priorDocuments)
                                CheckboxListTile(
                                  title: Text(
                                    '${previous['number']} · ${businessMoney(businessMap(previous['totals'])['gross'])}',
                                  ),
                                  value: previousIds.contains(previous['id']),
                                  onChanged: enabled
                                      ? (checked) => setState(() {
                                          checked == true
                                              ? previousIds.add(previous['id'])
                                              : previousIds.remove(
                                                  previous['id'],
                                                );
                                        })
                                      : null,
                                ),
                            ],
                          ),
                        Wrap(
                          spacing: 16,
                          runSpacing: 12,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Text(
                              'Positionen',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            OutlinedButton.icon(
                              onPressed: enabled ? () => position() : null,
                              icon: const Icon(Icons.add),
                              label: const Text('Position hinzufügen'),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        if (positions.isEmpty)
                          const BusinessEmpty(
                            'Noch keine Positionen',
                            'Erfassen Sie Menge, Einheit, Einzelpreis und Steuer je Leistung.',
                          ),
                        ReorderableListView.builder(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: positions.length,
                          onReorderItem: (oldIndex, newIndex) {
                            if (!enabled) return;
                            setState(() {
                              positions.insert(
                                newIndex,
                                positions.removeAt(oldIndex),
                              );
                            });
                          },
                          itemBuilder: (context, index) {
                            final p = positions[index];
                            return Card(
                              key: ValueKey(p),
                              child: ListTile(
                                title: Text('${p['description']}'),
                                subtitle: Text(
                                  '${p['quantity']} ${p['unit']} · ${businessMoney(p['unit_price_net'])} je ${p['price_base_quantity'] ?? '1'} ${p['unit']} netto · ${p['tax_rate']} %',
                                ),
                                onTap: enabled ? () => position(index) : null,
                                trailing: Padding(
                                  padding: const EdgeInsets.only(right: 26),
                                  child: IconButton(
                                    tooltip: 'Position entfernen',
                                    onPressed: enabled
                                        ? () => setState(
                                            () => positions.removeAt(index),
                                          )
                                        : null,
                                    icon: const Icon(Icons.delete_outline),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
                        const SizedBox(height: 20),
                        FilledButton.icon(
                          onPressed:
                              busy || !widget.session.canWrite('finance.write')
                              ? null
                              : save,
                          icon: Icon(
                            busy ? Icons.hourglass_top : Icons.save_outlined,
                          ),
                          label: Text(
                            uncertain
                                ? 'Dieselben Eingaben erneut senden'
                                : widget.templateMode
                                ? 'Vorlage speichern'
                                : 'Entwurf speichern',
                          ),
                        ),
                        if (uncertain)
                          const Notice(
                            'Die letzte Speicherung ist unbestätigt. Ihre Eingaben bleiben unverändert; erneutes Senden verwendet denselben Vorgang.',
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}

class BusinessDocumentPage extends StatefulWidget {
  const BusinessDocumentPage({
    super.key,
    required this.session,
    required this.id,
  });
  final BusinessSession session;
  final String id;
  @override
  State<BusinessDocumentPage> createState() => _BusinessDocumentPageState();
}

class _BusinessDocumentPageState extends State<BusinessDocumentPage> {
  Map<String, dynamic>? document;
  List<Map<String, dynamic>> signatures = [];
  String? error, notice;
  bool busy = false;
  int epoch = 0;
  final previews = <MailAttachmentPreviewController>[];
  bool get allowed =>
      widget.session.allowed && widget.session.can('finance.read');
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
      document = null;
      signatures = [];
      for (final preview in previews) preview.revoke();
    }
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    for (final preview in previews) preview.revoke();
    super.dispose();
  }

  Future<void> load() async {
    final current = ++epoch;
    try {
      final d = businessMap(
        await widget.session.read('/documents/${widget.id}'),
      );
      if (mounted && current == epoch && allowed) setState(() => document = d);
      if (d['status'] == 'final' &&
          [
            'offer',
            'order_confirmation',
            'delivery_note',
          ].contains(d['kind'])) {
        final values = businessItems(
          await widget.session.read('/documents/${widget.id}/signatures'),
        );
        if (mounted && current == epoch && allowed)
          setState(() => signatures = values);
      }
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    }
  }

  Future<void> action(String action, Map<String, dynamic> values) async {
    if (busy || document == null || !allowed) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = businessMap(
        await widget.session.command(
          'document-${widget.id}-$action',
          '/documents/${widget.id}/$action',
          {'revision': document!['revision'], ...values},
        ),
      );
      if (mounted && allowed) {
        if (result['id'] != null && result['id'] != widget.id) {
          await Navigator.push<void>(
            context,
            MaterialPageRoute(
              builder: (_) => BusinessDocumentPage(
                session: widget.session,
                id: result['id'],
              ),
            ),
          );
        } else {
          await load();
        }
      }
    } catch (e) {
      if (mounted && allowed) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> pdf({Map<String, dynamic>? signature}) async {
    if (busy || !allowed) return;
    setState(() => busy = true);
    final current = epoch;
    try {
      final Uint8List bytes = await widget.session.api.bytes(
        widget.session.path(
          signature == null
              ? '/documents/${widget.id}/pdf'
              : '/documents/${widget.id}/signatures/${signature['id']}/pdf',
        ),
        mediaType: 'application/pdf',
      );
      if (!mounted || current != epoch || !allowed) return;
      final hash = (await Sha256().hash(bytes)).bytes
          .map((v) => v.toRadixString(16).padLeft(2, '0'))
          .join();
      if (!mounted || current != epoch || !allowed) return;
      if (signature != null && signature['signed_pdf_sha256'] != hash)
        throw const ApiException(
          0,
          'Die Prüfsumme der unterzeichneten Fassung stimmt nicht.',
        );
      final controller = MailAttachmentPreviewController(
        VerifiedMailAttachment(
          bytes: bytes,
          filename: '${document?['number'] ?? 'beleg'}.pdf',
          mediaType: 'application/pdf',
          sha256: hash,
        ),
      );
      previews.add(controller);
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => MailAttachmentPreviewPage(
            controller: controller,
            mayView: () => mounted && allowed,
            exporter: exportMailAttachment,
          ),
        ),
      );
      controller.revoke();
      previews.remove(controller);
      controller.dispose();
    } catch (e) {
      if (mounted && allowed)
        setState(
          () => error = 'Die PDF-Vorschau konnte nicht geöffnet werden. $e',
        );
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> sign() async {
    final d = document;
    if (d == null || !allowed) return;
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => BusinessSignatureDialog(
        session: widget.session,
        path: '/documents/${widget.id}/sign',
        record: d,
        commercial: true,
      ),
    );
    if (mounted) await load();
  }

  Future<void> email() async {
    final d = document;
    if (d == null || busy || !widget.session.canWrite('finance.approve'))
      return;
    setState(() => busy = true);
    try {
      final preview = businessMap(
        await widget.session.read('/documents/${widget.id}/email-preview'),
      );
      if (!mounted || !allowed) return;
      final confirmed = await businessConfirm(
        context,
        title: 'E-Mail vor Versand prüfen',
        message:
            'An: ${preview['recipient']}\nBetreff: ${preview['subject']}\n\n${preview['text']}\n\nAnhänge: ${(preview['attachments'] as List? ?? []).map((a) => a['filename']).join(', ')}\n\nDer Empfang durch den Kunden wird nicht automatisch bestätigt.',
        action: 'Geprüfte E-Mail freigeben',
      );
      if (!confirmed || !mounted || !allowed) return;
      final result = businessMap(
        await widget.session.command(
          'document-mail-${widget.id}',
          '/documents/${widget.id}/email',
          {
            'revision': d['revision'],
            'confirmation': true,
            'preview_sha256': preview['preview_sha256'],
          },
        ),
      );
      if (mounted && allowed)
        setState(
          () => notice = result['accepted_by_server'] == true
              ? 'Vom Mailserver angenommen. Der Empfang durch den Kunden ist nicht bestätigt.'
              : result['status'] == 'unknown' || result['status'] == 'sending'
              ? 'Versandstand unklar. Bitte den Versand abgleichen; nicht erneut versenden.'
              : 'Versandfreigabe gespeichert. Der Versand ist noch nicht bestätigt.',
        );
    } catch (e) {
      if (mounted && allowed) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> cancel() async {
    final d = document;
    if (d == null || !widget.session.canWrite('finance.issue')) return;
    String? created;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Stornoentwurf erstellen',
        fields: const [
          BusinessField(
            'reason',
            'Stornogrund',
            type: BusinessInput.multiline,
            required: true,
          ),
        ],
        onSave: (values) async {
          final result = businessMap(
            await widget.session.command(
              'cancel-${widget.id}',
              '/documents/${widget.id}/cancel',
              {'revision': d['revision'], ...values},
            ),
          );
          created = result['id'];
        },
      ),
    );
    if (mounted && allowed && created != null)
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) =>
              BusinessDocumentPage(session: widget.session, id: created!),
        ),
      );
    if (mounted && allowed) await load();
  }

  @override
  Widget build(BuildContext context) {
    final d = document;
    final draft = d?['status'] == 'draft';
    final totals = businessMap(d?['totals']);
    return Scaffold(
      appBar: AppBar(
        title: Text(
          allowed
              ? '${d?['number'] ?? businessDocumentKinds[d?['kind']] ?? 'Beleg'}'
              : 'Beleg',
        ),
      ),
      body: !allowed
          ? const Center(child: Text('Der Zugang ist nicht mehr verfügbar.'))
          : d == null
          ? Center(
              child: error == null
                  ? const CircularProgressIndicator()
                  : Text(error!),
            )
          : ListView(
              padding: const EdgeInsets.all(24),
              children: [
                Text(
                  '${d['title']}',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  '${businessDocumentKinds[d['kind']] ?? d['kind']} · ${businessDocumentStates[d['status']] ?? d['status']} · ${businessDate(d['issue_date'])}',
                ),
                const SizedBox(height: 16),
                if (!draft)
                  const Notice(
                    'Unveränderlich festgeschrieben. Eine Korrektur erfolgt mit einem eigenen, verknüpften Beleg.',
                  ),
                if (error != null) Notice(error!, error: true),
                if (notice != null) Notice(notice!),
                if (busy) const LinearProgressIndicator(),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    if (draft && widget.session.canWrite('finance.write'))
                      OutlinedButton.icon(
                        onPressed: busy
                            ? null
                            : () async {
                                await Navigator.push<void>(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => BusinessDocumentEditor(
                                      session: widget.session,
                                      document: d,
                                    ),
                                  ),
                                );
                                if (mounted) await load();
                              },
                        icon: const Icon(Icons.edit_outlined),
                        label: const Text('Entwurf bearbeiten'),
                      ),
                    if (draft && widget.session.canWrite('finance.issue'))
                      FilledButton.icon(
                        onPressed: busy
                            ? null
                            : () async {
                                if (await businessConfirm(
                                      context,
                                      title: 'Beleg festschreiben?',
                                      message: 'Die finale Fassung und ihre Ausgabenummer können danach nicht geändert werden. Der Versand wird damit noch nicht ausgelöst.',
                                      action: 'Festschreiben',
                                    ) &&
                                    mounted)
                                  await action('finalize', {});
                              },
                        icon: const Icon(Icons.lock_outline),
                        label: const Text('Festschreiben'),
                      ),
                    if (!draft)
                      OutlinedButton.icon(
                        onPressed: busy ? null : pdf,
                        icon: const Icon(Icons.picture_as_pdf_outlined),
                        label: const Text('PDF öffnen'),
                      ),
                    if (!draft &&
                        [
                          'offer',
                          'order_confirmation',
                          'delivery_note',
                        ].contains(d['kind']) &&
                        widget.session.canWrite('documents.write'))
                      OutlinedButton.icon(
                        onPressed: busy ? null : sign,
                        icon: const Icon(Icons.draw_outlined),
                        label: const Text('Fassung unterschreiben'),
                      ),
                    if (!draft && widget.session.canWrite('finance.approve'))
                      OutlinedButton.icon(
                        onPressed: busy ? null : email,
                        icon: const Icon(Icons.mail_outline),
                        label: const Text('E-Mail prüfen'),
                      ),
                    if (!draft &&
                        d['kind'] != 'cancellation' &&
                        widget.session.canWrite('finance.issue'))
                      TextButton(
                        onPressed: busy ? null : cancel,
                        child: const Text('Stornoentwurf erstellen'),
                      ),
                    if (widget.session.canWrite('finance.write'))
                      for (final target in ['order_confirmation', 'invoice'])
                        if (target != d['kind'] &&
                            (target != 'invoice' ||
                                widget.session.canWrite('finance.write')))
                          OutlinedButton(
                            onPressed: busy
                                ? null
                                : () => action('convert', {
                                    'target_kind': target,
                                  }),
                            child: Text(
                              'In ${businessDocumentKinds[target]} umwandeln',
                            ),
                          ),
                  ],
                ),
                const SizedBox(height: 24),
                for (final signature in signatures)
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.verified_outlined),
                      title: Text('Unterzeichnet von ${signature['signer']}'),
                      subtitle: Text(
                        businessDate(signature['signed_at'], time: true),
                      ),
                      trailing: const Icon(Icons.picture_as_pdf_outlined),
                      onTap: busy ? null : () => pdf(signature: signature),
                    ),
                  ),
                for (final p in (d['positions'] as List? ?? []).map(
                  businessMap,
                ))
                  Card(
                    child: ListTile(
                      title: Text('${p['description']}'),
                      subtitle: Text(
                        '${p['quantity']} ${p['unit']} · ${businessMoney(p['unit_price_net'])} je ${p['price_base_quantity'] ?? '1'} ${p['unit']} netto · ${p['tax_rate']} % Umsatzsteuer',
                      ),
                    ),
                  ),
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Netto: ${businessMoney(totals['net'])}'),
                        Text('Umsatzsteuer: ${businessMoney(totals['tax'])}'),
                        if (totals['labor_gross'] != null)
                          Text(
                            'Lohn inklusive Umsatzsteuer: ${businessMoney(totals['labor_gross'])}',
                          ),
                        if (totals['material_gross'] != null)
                          Text(
                            'Material inklusive Umsatzsteuer: ${businessMoney(totals['material_gross'])}',
                          ),
                        const SizedBox(height: 8),
                        Text(
                          'Gesamt: ${businessMoney(totals['gross'])}',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        if (totals['payable'] != null)
                          Text(
                            'Zu zahlen: ${businessMoney(totals['payable'])}',
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}

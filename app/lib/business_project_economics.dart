import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_documents.dart';
import 'business_project_receipts.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const projectCostCategories = <String, String>{
  'external_service': 'Fremdleistungen',
  'machine': 'Maschinenkosten',
  'other': 'Sonstige Kosten',
  'stock_material': 'Lagermaterial – bereits über Entnahme erfasst',
  'excluded': 'Nicht als Projektkosten berücksichtigen',
};
const _classificationLabels = {
  'unreviewed': 'Belegprüfung fehlt',
  'unclassified': 'Kosteneinordnung fehlt',
  'current': 'Aktuell eingeordnet',
  'source_changed': 'Belegprüfung geändert – neue Einordnung erforderlich',
};

bool projectEconomicsReadable(BusinessSession session) =>
    session.projectId != null &&
    session.can('finance.read') &&
    session.hasFeature('project_economics') &&
    session.hasModule('project_economics');

String projectCostMoney(String input) {
  final value = businessDecimal(input);
  if (!RegExp(r'^\d+(?:\.\d{1,2})?$').hasMatch(value)) {
    throw const FormatException(
      'Bitte einen nicht negativen EUR-Betrag mit höchstens zwei Nachkommastellen eingeben.',
    );
  }
  final parts = value.split('.');
  return '${BigInt.parse(parts.first)}.${(parts.length == 2 ? parts[1] : '').padRight(2, '0')}';
}

BigInt _cents(String value) =>
    BigInt.parse(projectCostMoney(value).replaceAll('.', ''));
String _allocationsKey(dynamic rows) {
  final values = businessItems(rows)
    ..sort((a, b) => '${a['category']}'.compareTo('${b['category']}'));
  return jsonEncode([
    for (final row in values)
      {'category': row['category'], 'amount_net': row['amount_net']},
  ]);
}

void Function(dynamic) projectCostReceiptValidator(
  Map<String, dynamic> expected,
  Map<String, dynamic> source,
) {
  final frozen = Map<String, dynamic>.from(jsonDecode(jsonEncode(expected)));
  final sourceHash = source['source_hash'],
      originalHash = source['original_sha256'];
  return (dynamic value) {
    final entry = businessMap(value),
        proof = businessMap(businessMap(value)['source']);
    if (entry['project_id'] != frozen['project_id'] ||
        entry['receipt_id'] != frozen['receipt_id'] ||
        entry['source_revision'] != frozen['source_revision'] ||
        entry['revision'] != frozen['expected_revision'] + 1 ||
        entry['reason'] != frozen['reason'] ||
        _allocationsKey(entry['allocations']) !=
            _allocationsKey(frozen['allocations']) ||
        proof['source_hash'] != sourceHash ||
        proof['original_sha256'] != originalHash ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch('${entry['id']}') ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch('${entry['entry_hash']}')) {
      throw const ApiException(
        0,
        'Die Empfangsbestätigung stimmt nicht mit der geprüften Einordnung überein. Der ursprüngliche Auftrag bleibt erhalten.',
      );
    }
  };
}

class BusinessProjectEconomicsPage extends StatefulWidget {
  const BusinessProjectEconomicsPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessProjectEconomicsPage> createState() =>
      _BusinessProjectEconomicsPageState();
}

class _BusinessProjectEconomicsPageState
    extends State<BusinessProjectEconomicsPage> {
  Map<String, dynamic>? summary;
  List<Map<String, dynamic>> receipts = [];
  bool loading = false, denied = false;
  String? error;
  int epoch = 0;
  Object? generation;
  bool get readable => projectEconomicsReadable(widget.session) && !denied;
  String get project => widget.session.projectId!;
  @override
  void initState() {
    super.initState();
    generation = widget.session.generation;
    widget.session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!projectEconomicsReadable(widget.session) ||
        generation != widget.session.generation) {
      epoch++;
      summary = null;
      receipts = [];
      loading = false;
      generation = widget.session.generation;
    }
    setState(() {});
  }

  Future<void> load({bool refreshRights = false}) async {
    if (refreshRights) {
      await widget.session.load();
      if (!mounted) return;
      denied = false;
    }
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      if (!readable) return;
      final results = await Future.wait([
        widget.session.read(widget.session.query('/project-economics')),
        widget.session.read(widget.session.query('/project-economics/sources')),
      ]);
      final value = businessMap(results[0]),
          receiptRows = businessItems(results[1]);
      if (value['project_id'] != project ||
          value['currency'] != 'EUR' ||
          value['valuation_basis'] != 'document_net' ||
          value['tax_result_available'] != false ||
          receiptRows.any((row) => row['project_id'] != project) ||
          [
            'budget',
            'costs',
            'revenue',
            'payments',
            'result',
            'sources',
          ].any((key) => value[key] is! Map)) {
        throw const ApiException(
          0,
          'Die Projektübersicht konnte nicht eindeutig bestätigt werden.',
        );
      }
      if (mounted && current == epoch && readable)
        setState(() {
          summary = value;
          receipts = receiptRows;
        });
    } on ApiException catch (e) {
      if (!mounted || current != epoch) return;
      if ([403, 404].contains(e.status)) {
        denied = true;
        summary = null;
        receipts = [];
      }
      setState(() => error = '$e');
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> incoming([String? id]) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => BusinessProjectReceiptsPage(
          session: widget.session,
          initialReceiptId: id,
        ),
      ),
    );
    if (mounted && readable) await load();
  }

  Future<void> classify(Map<String, dynamic> source) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) =>
            BusinessProjectCostEditor(session: widget.session, source: source),
      ),
    );
    if (mounted && readable) await load();
  }

  Widget metric(String label, dynamic value) => Card(
    child: ListTile(
      title: Text(label),
      subtitle: Text(
        businessMoney(value),
        style: Theme.of(context).textTheme.titleLarge,
      ),
    ),
  );
  Widget metricSection(
    String title,
    Map<String, dynamic> values,
    Map<String, String> fields,
  ) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Padding(
        padding: const EdgeInsets.only(top: 20, bottom: 8),
        child: Text(title, style: Theme.of(context).textTheme.titleLarge),
      ),
      for (final field in fields.entries)
        metric(field.value, values[field.key]),
    ],
  );
  Future<void> sourceDetails(String kind, Map<String, dynamic> row) async {
    if (!readable) return;
    if (kind == 'documents' && row['id'] is String) {
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) =>
              BusinessDocumentPage(session: widget.session, id: row['id']),
        ),
      );
      return;
    }
    if (kind == 'receipt_allocations' && row['receipt_id'] is String) {
      await incoming(row['receipt_id']);
      return;
    }
    // These are the server-authorized project projections; opening them does
    // not silently widen financial rights into personnel or global inventories.
    await showDialog<void>(
      context: context,
      builder: (_) => _ProjectSourceDialog(session: widget.session, row: row),
    );
  }

  Future<void> budget() async {
    if (!readable ||
        !widget.session.canWrite('finance.write') ||
        !widget.session.sectionEnabled('material'))
      return;
    final revision = businessMap(summary?['budget'])['revision'];
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Projektbudget festlegen',
        readPermission: 'finance.read',
        writePermission: 'finance.write',
        pendingKey: 'project-economics-budget-$project',
        fields: const [
          BusinessField(
            'material_net',
            'Material netto (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'labor_net',
            'Lohn netto (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'machine_net',
            'Maschinen netto (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'other_net',
            'Sonstiges netto (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
        ],
        onSave: (values) async {
          await widget.session.command(
            'project-economics-budget-$project',
            '/budgets',
            {
              ...values,
              'project_id': project,
              if (revision is int && revision > 0) 'revision': revision,
            },
          );
        },
        saveLabel: 'Neue Budgetfassung speichern',
      ),
    );
    if (mounted && readable) await load();
  }

  Future<void> changeOrder() async {
    if (!readable ||
        !widget.session.canWrite('finance.write') ||
        !widget.session.sectionEnabled('material'))
      return;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Budgetnachtrag erfassen',
        readPermission: 'finance.read',
        writePermission: 'finance.write',
        pendingKey: 'project-economics-change-$project',
        fields: [
          const BusinessField('title', 'Begründung / Nachtrag', required: true),
          const BusinessField(
            'amount_net',
            'Zusätzliches Budget netto (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          if (widget.session.canWrite('finance.approve'))
            const BusinessField(
              'approved',
              'Nachtrag ausdrücklich freigeben',
              type: BusinessInput.toggle,
              initial: false,
            ),
        ],
        onSave: (values) async {
          await widget.session.command(
            'project-economics-change-$project',
            '/projects/$project/changes',
            {'project_id': project, ...values},
          );
        },
      ),
    );
    if (mounted && readable) await load();
  }

  @override
  Widget build(BuildContext context) {
    if (!readable)
      return ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const BusinessEmpty(
            'Projektwirtschaftlichkeit nicht freigegeben',
            'Für die Projektübersicht werden aktuelle Finanzrechte benötigt.',
          ),
          if (error != null) Notice(error!, error: true),
          OutlinedButton(
            onPressed: loading ? null : () => load(refreshRights: true),
            child: const Text('Berechtigungen neu prüfen'),
          ),
        ],
      );
    final d = summary;
    final costs = businessMap(d?['costs']), totals = businessMap(d?['result']);
    final payments = businessMap(d?['payments']);
    final sources = businessMap(d?['sources']);
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(
          'Projektwirtschaftlichkeit',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: 12),
        const Notice(
          'Kosten und Umsatz werden mit den Nettobeträgen der Belege verglichen. Zahlungen stehen getrennt in Brutto. Das ist keine EÜR und kein steuerlicher Gewinn; nicht erfasste Vorgänge können weiterhin fehlen.',
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            FilledButton.icon(
              onPressed: () => incoming(),
              icon: const Icon(Icons.receipt_long_outlined),
              label: const Text('Eingangsbelege erfassen und prüfen'),
            ),
            OutlinedButton.icon(
              onPressed: loading ? null : load,
              icon: const Icon(Icons.refresh),
              label: const Text('Aktualisieren'),
            ),
            if (widget.session.canWrite('finance.write') &&
                widget.session.sectionEnabled('material')) ...[
              OutlinedButton(
                onPressed: d == null ? null : budget,
                child: const Text('Budget festlegen'),
              ),
              OutlinedButton(
                onPressed: d == null ? null : changeOrder,
                child: const Text('Budgetnachtrag erfassen'),
              ),
            ],
          ],
        ),
        if (loading) const LinearProgressIndicator(),
        if (error != null) Notice(error!, error: true),
        if (d != null) ...[
          for (final issue in businessItems(d['issues'] ?? []))
            Card(
              child: ListTile(
                leading: const Icon(Icons.info_outline),
                title: Text('${issue['message']}'),
                trailing: receipts.any((r) => r['id'] == issue['source_id'])
                    ? TextButton(
                        onPressed: () => incoming(issue['source_id']),
                        child: const Text('Beleg öffnen'),
                      )
                    : null,
              ),
            ),
          metricSection(
            'Budget und erfasste Kosten',
            businessMap(d['budget']),
            const {
              'base_net': 'Gespeichertes Budget',
              'approved_changes_net': 'Freigegebene Nachträge',
              'total_net': 'Budget einschließlich Nachträge',
              'remaining_net': 'Verbleibendes Budget für erfasste Quellen',
            },
          ),
          metricSection('Erfasste Istkosten', costs, const {
            'material_net': 'Materialentnahmen',
            'labor_net': 'Genehmigte Zeitkosten',
            'external_service_net': 'Fremdleistungen',
            'machine_net': 'Maschinenkosten',
            'other_net': 'Sonstige Kosten',
            'total_net': 'Summe erfasster Kosten',
          }),
          metricSection('Rechnungsumsatz', businessMap(d['revenue']), const {
            'invoiced_net': 'Rechnungen netto',
            'credited_net': 'Korrekturen netto',
            'revenue_net': 'Rechnungsumsatz nach Korrekturen',
          }),
          metric(
            'Belegnetto-Deckungsbeitrag der erfassten Quellen',
            totals['document_net_contribution'],
          ),
          if (totals['complete_for_recorded_sources'] != true)
            const Notice(
              'Für erfasste Quellen fehlen bestätigte Bewertungen oder Einordnungen. Deckungsbeitrag und verbleibendes Budget werden erst nach Klärung ausgewiesen.',
              error: true,
            ),
          metricSection(
            'Tatsächliche Zahlungen und offene Posten',
            payments,
            const {
              'receipts_gross': 'Zugeordnete Kundenzahlungen brutto',
              'refunds_gross': 'Kundenerstattungen brutto',
              'net_inflow_gross': 'Kundenzahlungen nach Erstattungen',
              'supplier_outflows_gross':
                  'Bestätigte Lieferantenauszahlungen brutto',
              'cash_balance_gross': 'Saldo der erfassten Projektzahlungen',
              'open_gross': 'Offene Kundenforderungen brutto',
            },
          ),
          if (payments['complete'] != true)
            const Notice(
              'Lieferantenauszahlungen sind in dieser Ansicht nicht vollständig freigegeben oder bestätigt. Ein fehlender Betrag bedeutet nicht null.',
            ),
          Padding(
            padding: const EdgeInsets.only(top: 24, bottom: 8),
            child: Text(
              'Eingangsbelege und Kosteneinordnung',
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ),
          if (receipts.isEmpty)
            const BusinessEmpty(
              'Noch keine Eingangsbelege',
              'Belegoriginal erfassen, Angaben prüfen und den Nettobetrag ausdrücklich einordnen.',
            ),
          for (final source in receipts)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${source['vendor'] ?? source['filename']}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      '${source['invoice_number'] ?? source['filename']} · ${businessMoney(source['net'])} netto',
                    ),
                    Text(
                      _classificationLabels[source['classification_status']] ??
                          'Einordnung prüfen',
                    ),
                    Wrap(
                      spacing: 8,
                      children: [
                        TextButton(
                          onPressed: () => incoming(source['id']),
                          child: const Text('Beleg und Original öffnen'),
                        ),
                        if (widget.session.canWrite('finance.write') &&
                            widget.session.canWrite('finance.approve') &&
                            widget.session.sectionEnabled('finance') &&
                            source['classification_status'] != 'unreviewed')
                          OutlinedButton(
                            onPressed: () => classify(source),
                            child: Text(
                              widget.session.pending(
                                    'project-economics-$project-${source['id']}',
                                  )
                                  ? 'Unbestätigte Einordnung öffnen'
                                  : source['latest_entry'] == null
                                  ? 'Kosten einordnen'
                                  : 'Einordnung / Korrektur',
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          for (final kind in const {
            'material_movements': 'Materialnachweise',
            'approved_times': 'Zeitnachweise',
            'approved_changes': 'Freigegebene Nachträge',
            'receipt_allocations': 'Bestätigte Belegeinordnungen',
            'documents': 'Rechnungsbelege',
            'payment_allocations': 'Kundenzahlungsnachweise',
            'supplier_payments': 'Lieferantenzahlungsnachweise',
          }.entries)
            ExpansionTile(
              title: Text(kind.value),
              children: [
                for (final row in businessItems(sources[kind.key] ?? []))
                  ListTile(
                    title: Text(
                      '${row['number'] ?? row['vendor'] ?? row['article_snapshot']?['name'] ?? row['work_date'] ?? row['reference'] ?? row['id'] ?? row['entry_id'] ?? 'Nachweis'}',
                    ),
                    subtitle: Text(
                      '${row['cost_net'] ?? row['amount'] ?? row['net'] ?? row['amount_net'] ?? row['booking_date'] ?? row['created_at'] ?? ''}',
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => sourceDetails(kind.key, row),
                  ),
              ],
            ),
        ],
      ],
    );
  }
}

class _ProjectSourceDialog extends StatefulWidget {
  const _ProjectSourceDialog({required this.session, required this.row});
  final BusinessSession session;
  final Map<String, dynamic> row;
  @override
  State<_ProjectSourceDialog> createState() => _ProjectSourceDialogState();
}

class _ProjectSourceDialogState extends State<_ProjectSourceDialog> {
  late final Object? generation;
  @override
  void initState() {
    super.initState();
    generation = widget.session.generation;
    widget.session.addListener(changed);
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Projektbezogener Nachweis'),
    content: SingleChildScrollView(
      child:
          projectEconomicsReadable(widget.session) &&
              generation == widget.session.generation
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Diese Daten stammen aus der aktuell freigegebenen Projektübersicht.',
                ),
                for (final entry in widget.row.entries.where(
                  (e) => e.value != null && e.value is! List && e.value is! Map,
                ))
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: SelectableText(
                      '${const {'id': 'Nachweis', 'entry_id': 'Zeiteintrag', 'work_date': 'Arbeitstag', 'net_seconds': 'Genehmigte Sekunden', 'cost_minor': 'Historische Kosten in Cent', 'cost_net': 'Kosten netto', 'quantity': 'Menge', 'kind': 'Art', 'created_at': 'Erfasst', 'booking_date': 'Buchungstag', 'reference': 'Referenz', 'amount': 'Betrag', 'project_id': 'Projekt'}[entry.key] ?? entry.key}: ${entry.value}',
                    ),
                  ),
              ],
            )
          : const Text('Der Nachweis ist nicht mehr freigegeben.'),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Schließen'),
      ),
    ],
  );
}

class BusinessProjectCostEditor extends StatefulWidget {
  const BusinessProjectCostEditor({
    super.key,
    required this.session,
    required this.source,
  });
  final BusinessSession session;
  final Map<String, dynamic> source;
  @override
  State<BusinessProjectCostEditor> createState() =>
      _BusinessProjectCostEditorState();
}

class _BusinessProjectCostEditorState extends State<BusinessProjectCostEditor> {
  final amounts = {
    for (final category in projectCostCategories.keys)
      category: TextEditingController(),
  };
  final reason = TextEditingController();
  Map<String, dynamic>? preview, body;
  List<Map<String, dynamic>> history = [];
  String? error, success;
  bool busy = false, accepted = false, denied = false;
  int epoch = 0;
  late final Object? generation;
  String get project => widget.session.projectId!;
  String get receipt => widget.source['id'];
  String get key => 'project-economics-$project-$receipt';
  bool get pending => widget.session.pending(key);
  bool get readable => projectEconomicsReadable(widget.session) && !denied;
  bool get writable =>
      readable &&
      widget.session.canWrite('finance.write') &&
      widget.session.canWrite('finance.approve') &&
      widget.session.sectionEnabled('finance');
  @override
  void initState() {
    super.initState();
    generation = widget.session.generation;
    widget.session.addListener(changed);
    final waiting = widget.session.pendingCommandValues(
      key,
      path: '/project-economics/confirm',
    );
    final initial = waiting ?? businessMap(widget.source['latest_entry']);
    reason.text = '${initial['reason'] ?? ''}';
    for (final allocation in businessItems(initial['allocations'] ?? []))
      amounts[allocation['category']]?.text = '${allocation['amount_net']}';
    if (waiting != null) body = waiting;
    loadHistory();
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    reason.dispose();
    for (final c in amounts.values) c.dispose();
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!projectEconomicsReadable(widget.session) ||
        generation != widget.session.generation) {
      epoch++;
      denied = true;
      preview = null;
      history = [];
      for (final c in amounts.values) c.clear();
      reason.clear();
    }
    setState(() {});
  }

  Future<void> loadHistory() async {
    final current = epoch;
    try {
      final rows = businessItems(
        await widget.session.read(
          widget.session.query('/project-economics/receipts/$receipt'),
        ),
      );
      if (rows.any(
        (row) => row['project_id'] != project || row['receipt_id'] != receipt,
      ))
        throw const ApiException(
          0,
          'Die Einordnungshistorie gehört nicht zu diesem Projektbeleg.',
        );
      if (mounted && current == epoch && readable)
        setState(() => history = rows);
    } on ApiException catch (e) {
      if (mounted && current == epoch) {
        if ([403, 404].contains(e.status)) denied = true;
        setState(() => error = '$e');
      }
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    }
  }

  Future<void> check() async {
    if (!writable || busy || pending) return;
    final current = ++epoch, generation = widget.session.generation;
    setState(() {
      busy = true;
      error = null;
      success = null;
      preview = null;
      accepted = false;
    });
    try {
      final allocations = <Map<String, dynamic>>[];
      var total = BigInt.zero;
      for (final entry in amounts.entries) {
        if (entry.value.text.trim().isEmpty) continue;
        final amount = projectCostMoney(entry.value.text);
        final minor = _cents(amount);
        if (minor > BigInt.zero) {
          allocations.add({'category': entry.key, 'amount_net': amount});
          total += minor;
        }
      }
      if (total != _cents('${widget.source['net']}'))
        throw const FormatException(
          'Die Summe muss genau dem geprüften Nettobetrag entsprechen. Lagermaterial und ausgeschlossene Beträge ebenfalls ausdrücklich zuordnen.',
        );
      if (reason.text.trim().isEmpty)
        throw const FormatException(
          'Bitte die Einordnung oder Korrektur begründen.',
        );
      final values = <String, dynamic>{
        'project_id': project,
        'receipt_id': receipt,
        'source_revision': widget.source['revision'],
        'expected_revision': widget.source['classification_revision'],
        'allocations': allocations,
        'reason': reason.text.trim(),
      };
      final result = businessMap(
        await widget.session.api.call(
          widget.session.path('/project-economics/preview'),
          values,
        ),
      );
      if (!mounted ||
          current != epoch ||
          !writable ||
          generation != widget.session.generation)
        return;
      if (result['project_id'] != project ||
          result['receipt_id'] != receipt ||
          result['source_revision'] != values['source_revision'] ||
          result['expected_revision'] != values['expected_revision'] ||
          result['reason'] != values['reason'] ||
          _allocationsKey(result['allocations']) !=
              _allocationsKey(allocations) ||
          !RegExp(r'^[a-f0-9]{64}$').hasMatch('${result['preview_hash']}'))
        throw const ApiException(
          0,
          'Die Vorschau stimmt nicht mit Ihrer Einordnung überein.',
        );
      final source = businessMap(result['source']);
      if (source['receipt_id'] != receipt ||
          source['net'] != widget.source['net'] ||
          source['original_sha256'] != widget.source['sha256'])
        throw const ApiException(
          0,
          'Der Vorschau fehlt die passende unveränderte Belegquelle.',
        );
      setState(() {
        preview = result;
        body = {
          ...values,
          'allocations': result['allocations'],
          'preview_hash': result['preview_hash'],
        };
      });
    } on ApiException catch (e) {
      if (e.status == 401) widget.session.revoke();
      if (mounted && current == epoch) {
        if ([403, 404].contains(e.status)) {
          denied = true;
          preview = null;
          history = [];
        }
        setState(() => error = '$e');
      }
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  Future<void> confirm() async {
    if (!writable ||
        busy ||
        (!pending && (!accepted || preview == null || body == null)))
      return;
    final current = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = businessMap(
        pending
            ? await widget.session.repeatProjectEconomicsCommand(
                project,
                receipt,
              )
            : await widget.session.command(
                key,
                '/project-economics/confirm',
                body!,
                validateResult: projectCostReceiptValidator(
                  body!,
                  businessMap(preview!['source']),
                ),
              ),
      );
      if (!mounted || current != epoch || !readable) return;
      if (result['project_id'] != project || result['receipt_id'] != receipt)
        throw const ApiException(
          0,
          'Die Bestätigung gehört nicht zu diesem Projektbeleg.',
        );
      setState(() {
        success = 'Die Einordnung ist als unveränderliche Fassung gespeichert.';
        preview = null;
        body = null;
        accepted = false;
      });
      await loadHistory();
    } on ApiException catch (e) {
      if (mounted && current == epoch) {
        if ([403, 404].contains(e.status)) {
          denied = true;
          preview = null;
          history = [];
        }
        setState(() => error = '$e');
      }
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Projektkosten einordnen')),
    body: !readable
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: BusinessEmpty(
              'Beleg nicht mehr freigegeben',
              'Rechte oder Datenstand haben sich geändert. Eine unbestätigte Übertragung bleibt erhalten. Projektübersicht aktualisieren und diesen Beleg erneut öffnen.',
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(
                '${widget.source['vendor'] ?? widget.source['filename']} · ${widget.source['invoice_number'] ?? ''}',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Text(
                'Aktuelle Belegprüfung ${widget.source['revision']}: ${businessMoney(widget.source['net'])} netto',
              ),
              const SizedBox(height: 12),
              const Notice(
                'Den vollständigen Nettobetrag ausdrücklich aufteilen. Lagermaterial wird bereits über Materialentnahmen bewertet und zählt hier nicht nochmals. Eine Korrektur ersetzt die aktuelle Einordnung durch eine neue nachvollziehbare Fassung; der Beleg und die alten Fassungen bleiben erhalten.',
              ),
              if (widget.source['status'] == 'rejected')
                const Notice(
                  'Dieser Beleg wurde abgelehnt. Eine Einordnung ist ausschließlich als begründete Abgrenzung möglich; bereits eingetragene Kostenkategorien müssen dafür geleert werden.',
                ),
              if (pending)
                const Notice(
                  'Die letzte Übertragung ist unbestätigt. Es wird ausschließlich derselbe Auftrag erneut gesendet.',
                ),
              if (error != null) Notice(error!, error: true),
              if (success != null) Notice(success!),
              if (busy) const LinearProgressIndicator(),
              for (final item in projectCostCategories.entries)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: TextField(
                    controller: amounts[item.key],
                    enabled:
                        writable &&
                        !busy &&
                        !pending &&
                        preview == null &&
                        success == null,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    decoration: InputDecoration(
                      labelText: '${item.value} (€ netto)',
                      helperText: item.key == 'excluded'
                          ? 'Bewusste Abgrenzung, kein Löschen des Originalbelegs.'
                          : null,
                    ),
                  ),
                ),
              const SizedBox(height: 12),
              TextField(
                controller: reason,
                enabled:
                    writable &&
                    !busy &&
                    !pending &&
                    preview == null &&
                    success == null,
                maxLength: 1000,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Begründung der Einordnung / Korrektur',
                ),
              ),
              if (preview == null && !pending && success == null)
                FilledButton(
                  onPressed: writable && !busy ? check : null,
                  child: const Text('Einordnung unverbindlich prüfen'),
                ),
              if (preview != null) ...[
                const SizedBox(height: 16),
                Text(
                  'Geprüfte Einordnung',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                for (final row in businessItems(preview!['allocations']))
                  ListTile(
                    title: Text(
                      projectCostCategories[row['category']] ?? 'Kategorie',
                    ),
                    trailing: Text(businessMoney(row['amount_net'])),
                  ),
                CheckboxListTile(
                  value: accepted,
                  onChanged: writable && !busy
                      ? (v) => setState(() => accepted = v == true)
                      : null,
                  title: const Text(
                    'Ich habe Beleg und vollständige Aufteilung geprüft und bestätige diese Projektkosteneinordnung.',
                  ),
                ),
                OutlinedButton(
                  onPressed: busy
                      ? null
                      : () => setState(() {
                          preview = null;
                          body = null;
                          accepted = false;
                        }),
                  child: const Text('Angaben bearbeiten'),
                ),
              ],
              if (pending || preview != null)
                FilledButton(
                  onPressed: writable && !busy && (pending || accepted)
                      ? confirm
                      : null,
                  child: Text(
                    pending
                        ? 'Unverändert erneut senden'
                        : 'Einordnung verbindlich festhalten',
                  ),
                ),
              const SizedBox(height: 24),
              Text(
                'Gespeicherte Fassungen',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              if (history.isEmpty)
                const Text('Noch keine gespeicherte Einordnung.'),
              for (final item in history)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Fassung ${item['revision']} · Belegprüfung ${item['source_revision']} · ${businessDate(item['created_at'], time: true)}',
                        ),
                        Text('${item['reason']}'),
                        for (final row in businessItems(item['allocations']))
                          Text(
                            '${projectCostCategories[row['category']] ?? row['category']}: ${businessMoney(row['amount_net'])}',
                          ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
  );
}

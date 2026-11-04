import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_catalog_prices.dart';
import 'business_widgets.dart';
import 'design.dart';

Widget _unavailableDialog(BuildContext context, String message) => Padding(
  padding: const EdgeInsets.all(24),
  child: Column(
    mainAxisSize: MainAxisSize.min,
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(message),
      const SizedBox(height: 16),
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Schließen'),
      ),
    ],
  ),
);

/// A server-calculated proposal. No client-side financial arithmetic is used.
class BusinessPricingEditor extends StatefulWidget {
  const BusinessPricingEditor({
    super.key,
    required this.session,
    this.initial,
    this.projectId,
    this.onFinanceDenied,
  });
  final BusinessSession session;
  final Map<String, dynamic>? initial;
  final String? projectId;
  final VoidCallback? onFinanceDenied;

  @override
  State<BusinessPricingEditor> createState() => _BusinessPricingEditorState();
}

class _BusinessPricingEditorState extends State<BusinessPricingEditor>
    with WidgetsBindingObserver {
  final form = GlobalKey<FormState>();
  final fields = <String, TextEditingController>{};
  final components = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> articles = [];
  Map<String, dynamic>? proposal;
  String kind = 'service';
  String? error, articleError;
  bool busy = false, accessDenied = false;
  int version = 0;
  CatalogPriceFlow? catalogFlow;
  Map<String, dynamic>? catalogSource, sourcePriceSelection;
  String? sourcePriceLabel;
  Object? catalogGeneration;

  bool get mayView =>
      !accessDenied &&
      widget.session.can('finance.read') &&
      widget.session.hasFeature('quote_pricing');
  bool get mayEdit =>
      mayView &&
      widget.session.canWrite('finance.write') &&
      widget.session.sectionEnabled('documents');

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    catalogGeneration = widget.session.generation;
    final initial = widget.initial ?? <String, dynamic>{};
    final pricing = businessMap(
      initial['pricing'] ?? businessMap(initial['pricing_snapshot'])['inputs'],
    );
    kind = initial['kind'] ?? pricing['kind'] ?? 'service';
    if (pricing['source_article_id'] != null)
      catalogSource = {
        'id': pricing['source_article_id'],
        'revision': pricing['source_article_revision'],
      };
    if (pricing['source_price_selection'] is Map)
      sourcePriceSelection = businessMap(pricing['source_price_selection']);
    for (final name in const [
      'description',
      'quantity',
      'unit',
      'tax_rate',
      'base_cost_net',
      'labor_hours',
      'hourly_cost_net',
      'overhead_percent',
      'overhead_amount',
      'markup_percent',
      'markup_amount',
      'surcharge_percent',
      'surcharge_amount',
    ]) {
      final value =
          ['description', 'quantity', 'unit', 'tax_rate'].contains(name)
          ? initial[name] ?? pricing[name]
          : pricing[name] ?? initial[name];
      fields[name] = TextEditingController(
        text:
            '${value ?? switch (name) {
                  'quantity' => '1',
                  'unit' => 'C62',
                  'tax_rate' => '19',
                  _ => '',
                }}',
      );
      fields[name]!.addListener(edited);
    }
    components.addAll((pricing['components'] as List? ?? []).map(businessMap));
    final historicalSources =
        (businessMap(initial['pricing_snapshot'])['source_articles'] as List? ??
                [])
            .map(businessMap)
            .toList();
    String? historicalLabel(Object? articleId, Map<String, dynamic> selection) {
      final snapshot = historicalSources
          .where((item) => item['id'] == articleId)
          .map((item) => businessMap(item['catalog_price_snapshot']))
          .where(
            (value) =>
                value['price_id'] == selection['price_id'] &&
                value['price_revision'] == selection['price_revision'],
          )
          .firstOrNull;
      return snapshot == null
          ? null
          : '${snapshot['source_name']} · ${catalogPriceLabel(businessMap(snapshot['price']))} · Preisstand ${snapshot['effective_on']}';
    }

    if (sourcePriceSelection != null)
      sourcePriceLabel = historicalLabel(
        catalogSource?['id'],
        sourcePriceSelection!,
      );
    for (final component in components) {
      final label = historicalLabel(
        component['article_id'],
        businessMap(component['price_selection']),
      );
      if (label != null) component['price_label'] = label;
    }
    widget.session.addListener(accessChanged);
    loadArticles();
  }

  void edited() {
    version++;
    if (mounted) setState(() => proposal = null);
  }

  void accessChanged() {
    if (!mounted) return;
    if (catalogGeneration != widget.session.generation) {
      accessDenied = true;
      catalogGeneration = widget.session.generation;
    }
    if (!mayView ||
        !mayEdit &&
            (sourcePriceSelection != null ||
                components.any((item) => item['price_selection'] != null))) {
      version++;
      catalogFlow?.dispose();
      catalogFlow = null;
      catalogSource = null;
      sourcePriceSelection = null;
      sourcePriceLabel = null;
      proposal = null;
      articles = [];
      components.clear();
      for (final field in fields.values) field.clear();
    }
    setState(() {});
  }

  Future<void> loadArticles() async {
    if (!mayView) return;
    try {
      final records = businessItems(await widget.session.read('/articles'));
      if (mounted && mayView)
        setState(
          () => articles = records.where((a) => a['active'] != false).toList(),
        );
    } on ApiException catch (e) {
      if (e.status == 401) {
        denyAccess();
        return;
      }
      if (mounted && mayView)
        setState(() {
          articles = [];
          articleError = e.status == 403 || e.status == 404
              ? 'Der globale Artikelstamm ist nicht freigegeben. Sie können die Kostenbasis manuell erfassen.'
              : e.message;
        });
    }
  }

  @override
  void didUpdateWidget(covariant BusinessPricingEditor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.projectId != widget.projectId) {
      oldWidget.session.removeListener(accessChanged);
      widget.session.addListener(accessChanged);
      catalogFlow?.dispose();
      accessDenied = true;
      accessChanged();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed && mounted) {
      accessDenied = true;
      accessChanged();
    }
  }

  void denyAccess() {
    if (!mounted) return;
    accessDenied = true;
    accessChanged();
    widget.onFinanceDenied?.call();
  }

  @override
  void dispose() {
    catalogFlow?.dispose();
    WidgetsBinding.instance.removeObserver(this);
    widget.session.removeListener(accessChanged);
    for (final field in fields.values) {
      field.removeListener(edited);
      field.clear();
      field.dispose();
    }
    super.dispose();
  }

  String decimal(String name) {
    final text = fields[name]!.text.trim();
    return text.isEmpty ? '0' : businessDecimal(text);
  }

  Map<String, dynamic> inputs() => {
    if (widget.projectId != null) 'project_id': widget.projectId,
    if (catalogSource != null) 'source_article_id': catalogSource!['id'],
    if (catalogSource != null)
      'source_article_revision': catalogSource!['revision'],
    if (sourcePriceSelection != null)
      'source_price_selection': sourcePriceSelection,
    for (final name in const [
      'base_cost_net',
      'labor_hours',
      'hourly_cost_net',
      'overhead_percent',
      'overhead_amount',
      'markup_percent',
      'markup_amount',
      'surcharge_percent',
      'surcharge_amount',
      'tax_rate',
      'quantity',
    ])
      if (name != 'base_cost_net' || sourcePriceSelection == null)
        name: decimal(name),
    'unit': fields['unit']!.text.trim(),
    'kind': kind,
    'components': [
      for (final component in components)
        {
          'article_id': component['article_id'],
          'article_revision': component['article_revision'],
          'quantity': component['quantity'],
          if (component['price_selection'] != null)
            'price_selection': component['price_selection'],
        },
    ],
  };

  Future<void> preview() async {
    if (busy || !mayEdit || !(form.currentState?.validate() ?? false)) return;
    if (fields['labor_hours']!.text.trim().isNotEmpty !=
        fields['hourly_cost_net']!.text.trim().isNotEmpty) {
      setState(
        () => error =
            'Bitte Arbeitszeit und internen Stundensatz gemeinsam angeben.',
      );
      return;
    }
    final current = version;
    setState(() {
      busy = true;
      error = null;
      proposal = null;
    });
    try {
      final result = businessMap(
        await widget.session.command(
          'pricing-${identityHashCode(this)}-$current',
          '/commercial/pricing/preview',
          inputs(),
        ),
      );
      if (!mounted || !mayEdit || current != version) return;
      if (result['inputs'] is! Map ||
          result['unit_price_net'] is! String ||
          result['unit_cost_net'] is! String ||
          !RegExp(r'^[a-f0-9]{64}$').hasMatch('${result['preview_hash']}')) {
        throw const ApiException(
          0,
          'Die Kalkulation konnte nicht sicher übernommen werden. Bitte erneut berechnen.',
        );
      }
      setState(() => proposal = result);
    } on ApiException catch (e) {
      if (!mounted || current != version || !mayView) return;
      if ([401, 403, 404].contains(e.status)) {
        denyAccess();
        return;
      }
      if (mounted && mayView && current == version)
        setState(() => error = e.message);
    } on FormatException catch (e) {
      if (mounted && current == version && mayView)
        setState(() => error = e.message);
    } finally {
      if (mounted && current == version && mayView)
        setState(() => busy = false);
    }
  }

  Future<void> chooseCatalogCost({bool component = false}) async {
    if (!mayEdit) return;
    final owner = widget.session;
    catalogFlow?.dispose();
    final flow = CatalogPriceFlow(
      context,
      owner,
      () => mounted && identical(owner, widget.session) && mayEdit,
    );
    catalogFlow = flow;
    try {
      await flow.fresh();
      Map<String, dynamic>? chosen;
      await flow.dialog<void>(
        (_) => BusinessEditor(
          session: owner,
          readPermission: 'finance.read',
          writePermission: 'finance.write',
          title: component
              ? 'Artikel zur Stückliste hinzufügen'
              : 'Basiskostenquelle wählen',
          fields: [
            BusinessField(
              'article_id',
              'Artikel',
              type: BusinessInput.choice,
              required: true,
              choices: {
                for (final a in articles)
                  '${a['id']}':
                      '${a['name']} · ${catalogPriceManaged(a) ? 'Datierten Einkaufspreis wählen' : businessMoney(a['cost_known'] == false ? null : a['cost_price_net']) + ' EK / ' + a['unit']}',
              },
            ),
            if (component)
              const BusinessField(
                'quantity',
                'Menge je Positionseinheit',
                type: BusinessInput.decimal,
                required: true,
              ),
          ],
          onSave: (values) async {
            chosen = values;
          },
        ),
      );
      if (!flow.valid || chosen == null) return;
      final article = articles.firstWhere(
        (item) => item['id'] == chosen!['article_id'],
      );
      CatalogPriceChoice? choice;
      if (catalogPriceManaged(article)) {
        choice = await flow.choose(article, 'purchase_net');
        if (choice == null) return;
      }
      await flow.fresh();
      if (!flow.valid) return;
      setState(() {
        if (component) {
          components.add({
            'article_id': article['id'],
            'article_revision': article['revision'],
            'quantity': chosen!['quantity'],
            'name': article['name'],
            if (choice != null) 'price_selection': choice.selection,
            if (choice != null) 'price_label': choice.label,
          });
        } else {
          catalogSource = article;
          sourcePriceSelection = choice?.selection;
          sourcePriceLabel = choice?.label;
          fields['base_cost_net']!.text = choice == null
              ? '${article['cost_price_net'] ?? ''}'
              : '';
        }
        version++;
        proposal = null;
      });
    } catch (e) {
      if (flow.valid) setState(() => error = '$e');
    } finally {
      flow.dispose();
      if (identical(catalogFlow, flow)) catalogFlow = null;
    }
  }

  Future<void> addComponent() => chooseCatalogCost(component: true);

  Widget input(
    String name,
    String label, {
    bool required = false,
    bool text = false,
    String? hint,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: TextFormField(
      key: ValueKey('pricing-$name'),
      controller: fields[name],
      enabled:
          mayEdit &&
          !busy &&
          (name != 'base_cost_net' || sourcePriceSelection == null),
      keyboardType: text
          ? null
          : const TextInputType.numberWithOptions(decimal: true),
      decoration: InputDecoration(
        labelText: label,
        helperText: hint,
        helperMaxLines: 3,
      ),
      validator: (value) {
        if ((value ?? '').trim().isEmpty)
          return required ? 'Bitte ausfüllen.' : null;
        if (!text) {
          try {
            final parsed = businessDecimal(value!);
            if (parsed.startsWith('-'))
              return 'Bitte eine positive Zahl oder 0 eingeben.';
          } catch (_) {
            return 'Bitte eine gültige Zahl eingeben.';
          }
        }
        return null;
      },
    ),
  );

  Widget amount(String label, Object? value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 5),
    child: Row(
      children: [
        Expanded(child: Text(label)),
        const SizedBox(width: 12),
        Text(businessMoney(value)),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final totals = businessMap(proposal?['totals']);
    final breakdown = businessMap(proposal?['breakdown']);
    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 650, maxHeight: 850),
        child: !mayView
            ? _unavailableDialog(
                context,
                'Die Kalkulation ist nicht mehr verfügbar. Bitte schließen Sie die Vorschau und prüfen Sie den Projektzugang oder die Artikelquelle.',
              )
            : Form(
                key: form,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(24, 16, 8, 8),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              'Position kalkulieren',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                          ),
                          IconButton(
                            onPressed: () => Navigator.pop(context),
                            tooltip: 'Schließen',
                            icon: const Icon(Icons.close),
                          ),
                        ],
                      ),
                    ),
                    Flexible(
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.fromLTRB(24, 8, 24, 20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Kosten je Positionseinheit erfassen. Preise werden erst nach Ihrer Übernahme in den Entwurf eingefügt.',
                            ),
                            const SizedBox(height: 20),
                            input(
                              'description',
                              'Beschreibung',
                              required: true,
                              text: true,
                            ),
                            input(
                              'quantity',
                              'Abrechnungsmenge',
                              required: true,
                            ),
                            input(
                              'unit',
                              'Einheit',
                              required: true,
                              text: true,
                              hint: 'C62 = Stück · HUR = Stunde · MTR = Meter',
                            ),
                            DropdownButtonFormField<String>(
                              initialValue: kind,
                              isExpanded: true,
                              decoration: const InputDecoration(
                                labelText: 'Kostenart',
                              ),
                              items: const [
                                DropdownMenuItem(
                                  value: 'labor',
                                  child: Text('Lohn'),
                                ),
                                DropdownMenuItem(
                                  value: 'material',
                                  child: Text('Material'),
                                ),
                                DropdownMenuItem(
                                  value: 'service',
                                  child: Text('Leistung'),
                                ),
                                DropdownMenuItem(
                                  value: 'machine',
                                  child: Text('Maschine'),
                                ),
                              ],
                              onChanged: mayEdit && !busy
                                  ? (value) {
                                      setState(() => kind = value!);
                                      edited();
                                    }
                                  : null,
                            ),
                            const SizedBox(height: 14),
                            input(
                              'tax_rate',
                              'Umsatzsteuer (%)',
                              required: true,
                            ),
                            const Divider(height: 30),
                            Text(
                              'Kostenbasis',
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            const SizedBox(height: 12),
                            input(
                              'base_cost_net',
                              'Weitere Basis-EK netto (€)',
                              required: sourcePriceSelection == null,
                              hint: 'Ohne die unten gewählten Artikel und Lohnkosten. Wenn keine weiteren Kosten anfallen, ausdrücklich 0 eingeben.',
                            ),
                            input(
                              'labor_hours',
                              'Arbeitszeit je Einheit (Stunden)',
                            ),
                            input(
                              'hourly_cost_net',
                              'Interner Stundensatz netto (€/h)',
                              hint: 'Interne Kosten, kein Abrechnungssatz.',
                            ),
                            const Text(
                              'Stückliste / Material',
                              style: TextStyle(fontWeight: FontWeight.w600),
                            ),
                            if (catalogPricesReadable(widget.session)) ...[
                              OutlinedButton(
                                onPressed:
                                    mayEdit && !busy && articles.isNotEmpty
                                    ? () => chooseCatalogCost()
                                    : null,
                                child: const Text(
                                  'Datierte Basiskostenquelle wählen',
                                ),
                              ),
                              if (sourcePriceSelection != null)
                                Text(
                                  sourcePriceLabel ??
                                      'Gewählter Einkaufspreis · Preisstand ${sourcePriceSelection!['effective_on']}',
                                ),
                              if (sourcePriceSelection != null)
                                const Text(
                                  'Basiskosten werden aus Rohbetrag und Bezugsmenge serverseitig berechnet.',
                                ),
                            ],
                            if (articleError != null)
                              Notice(
                                'Artikel konnten nicht geladen werden: $articleError',
                              ),
                            for (
                              var index = 0;
                              index < components.length;
                              index++
                            )
                              ListTile(
                                contentPadding: EdgeInsets.zero,
                                title: Text(
                                  '${components[index]['name'] ?? articles.where((a) => a['id'] == components[index]['article_id']).firstOrNull?['name'] ?? 'Hinterlegter Artikel'}',
                                ),
                                subtitle: Text(
                                  '${components[index]['quantity']} · Artikelstand ${components[index]['article_revision']}${components[index]['price_label'] != null
                                      ? '\n${components[index]['price_label']}'
                                      : components[index]['price_selection'] != null
                                      ? '\nPreisstand ${components[index]['price_selection']['effective_on']}'
                                      : ''}',
                                ),
                                trailing: IconButton(
                                  tooltip: 'Stücklistenartikel entfernen',
                                  icon: const Icon(Icons.remove_circle_outline),
                                  onPressed: mayEdit && !busy
                                      ? () => setState(() {
                                          components.removeAt(index);
                                          proposal = null;
                                          version++;
                                        })
                                      : null,
                                ),
                              ),
                            OutlinedButton.icon(
                              onPressed: mayEdit && !busy && articles.isNotEmpty
                                  ? addComponent
                                  : null,
                              icon: const Icon(Icons.add),
                              label: const Text('Artikel hinzufügen'),
                            ),
                            ExpansionTile(
                              tilePadding: EdgeInsets.zero,
                              title: const Text('Gemeinkosten und Aufschläge'),
                              subtitle: const Text(
                                'Leere Zusatzfelder werden nicht angesetzt.',
                              ),
                              children: [
                                input('overhead_percent', 'Gemeinkosten (%)'),
                                input(
                                  'overhead_amount',
                                  'Gemeinkosten zusätzlich (€)',
                                ),
                                input('markup_percent', 'Gewinnaufschlag (%)'),
                                input(
                                  'markup_amount',
                                  'Gewinnaufschlag zusätzlich (€)',
                                ),
                                input(
                                  'surcharge_percent',
                                  'Weiterer Zuschlag (%)',
                                ),
                                input(
                                  'surcharge_amount',
                                  'Weiterer Zuschlag zusätzlich (€)',
                                ),
                              ],
                            ),
                            if (error != null) Notice(error!, error: true),
                            if (proposal != null)
                              Card(
                                child: Padding(
                                  padding: const EdgeInsets.all(16),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'Kalkulationsvorschau',
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleMedium,
                                      ),
                                      amount(
                                        'Kosten je Einheit',
                                        proposal!['unit_cost_net'],
                                      ),
                                      for (final row in const {
                                        'base_cost_net':
                                            'Weitere Basis-EK je Einheit',
                                        'labor_cost_net':
                                            'Lohnkosten je Einheit',
                                        'component_cost_net':
                                            'Stückliste je Einheit',
                                        'overhead_net':
                                            'Gemeinkosten je Einheit',
                                        'markup_net':
                                            'Gewinnaufschlag je Einheit',
                                        'surcharge_net':
                                            'Weiterer Zuschlag je Einheit',
                                      }.entries)
                                        if (breakdown[row.key] != null)
                                          amount(row.value, breakdown[row.key]),
                                      amount(
                                        'Verkaufspreis je Einheit netto',
                                        proposal!['unit_price_net'],
                                      ),
                                      const Text(
                                        'Gemeinkosten auf die direkten Kosten; Gewinnaufschlag und weiterer Zuschlag jeweils auf die Kosten einschließlich Gemeinkosten.',
                                      ),
                                      const Divider(),
                                      amount('Gesamt netto', totals['net']),
                                      amount('Umsatzsteuer', totals['tax']),
                                      amount('Gesamt brutto', totals['gross']),
                                      amount(
                                        'Gewinn netto',
                                        totals['profit_net'],
                                      ),
                                      Text(
                                        totals['margin_percent'] == null
                                            ? 'Marge nicht berechenbar.'
                                            : 'Marge: ${'${totals['margin_percent']}'.replaceAll('.', ',')} %',
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            const SizedBox(height: 12),
                            Wrap(
                              spacing: 12,
                              runSpacing: 10,
                              children: [
                                OutlinedButton.icon(
                                  onPressed: mayEdit && !busy ? preview : null,
                                  icon: Icon(
                                    busy
                                        ? Icons.hourglass_top
                                        : Icons.calculate_outlined,
                                  ),
                                  label: const Text('Preis berechnen'),
                                ),
                                FilledButton(
                                  onPressed:
                                      mayEdit && !busy && proposal != null
                                      ? () {
                                          final current = proposal!;
                                          Navigator.pop(
                                            context,
                                            <String, dynamic>{
                                              if (widget.initial?['id'] != null)
                                                'id': widget.initial!['id'],
                                              'description':
                                                  fields['description']!.text
                                                      .trim(),
                                              'quantity':
                                                  fields['quantity']!.text
                                                      .trim()
                                                      .isEmpty
                                                  ? '1'
                                                  : businessDecimal(
                                                      fields['quantity']!.text,
                                                    ),
                                              'unit': fields['unit']!.text
                                                  .trim(),
                                              'tax_rate': businessDecimal(
                                                fields['tax_rate']!.text,
                                              ),
                                              'kind': kind,
                                              'unit_price_net':
                                                  current['unit_price_net'],
                                              'cost_price_net':
                                                  current['unit_cost_net'],
                                              'pricing': businessMap(
                                                current['inputs'],
                                              ),
                                              'pricing_hash':
                                                  current['preview_hash'],
                                              'price_confirmation': true,
                                            },
                                          );
                                        }
                                      : null,
                                  child: const Text(
                                    'Kalkulierten Preis übernehmen',
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
      ),
    );
  }
}

/// Keeps quantities and source proof on the server; the editor only chooses
/// measured lines and explicitly supplies their commercial prices.
class BusinessMeasurementTransferEditor extends StatefulWidget {
  const BusinessMeasurementTransferEditor({
    super.key,
    required this.session,
    required this.projectId,
  });
  final BusinessSession session;
  final String projectId;
  @override
  State<BusinessMeasurementTransferEditor> createState() =>
      _BusinessMeasurementTransferEditorState();
}

class _BusinessMeasurementTransferEditorState
    extends State<BusinessMeasurementTransferEditor> {
  List<Map<String, dynamic>> measurements = [];
  Map<String, dynamic>? selected, proposal;
  final lineInputs = <int, Map<String, dynamic>>{};
  String? error;
  bool loading = true, busy = false, accessDenied = false;
  int version = 0;
  bool get mayView =>
      !accessDenied &&
      widget.session.can('finance.read') &&
      widget.session.can('documents.read') &&
      widget.session.hasFeature('measurement_transfer');
  bool get mayEdit =>
      mayView &&
      widget.session.canWrite('finance.write') &&
      widget.session.sectionEnabled('documents');

  @override
  void initState() {
    super.initState();
    widget.session.addListener(accessChanged);
    load();
  }

  void accessChanged() {
    if (!mounted) return;
    if (!mayView) {
      selected = null;
      proposal = null;
      measurements = [];
      lineInputs.clear();
    }
    setState(() {});
  }

  bool hideOnDenied(ApiException error) {
    if (![401, 403, 404].contains(error.status)) return false;
    accessDenied = true;
    accessChanged();
    return true;
  }

  @override
  void dispose() {
    widget.session.removeListener(accessChanged);
    super.dispose();
  }

  Future<void> load() async {
    if (!mayView) {
      if (mounted) setState(() => loading = false);
      return;
    }
    try {
      final items = businessItems(
        await widget.session.read(
          '/measurements?${Uri(queryParameters: {'project_id': widget.projectId}).query}',
        ),
      );
      if (mounted && mayView)
        setState(
          () => measurements = items
              .where((m) => m['project_id'] == widget.projectId)
              .toList(),
        );
    } on ApiException catch (e) {
      if (hideOnDenied(e)) return;
      if (mounted && mayView) setState(() => error = e.message);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> select(String id) async {
    final current = ++version;
    setState(() {
      selected = null;
      proposal = null;
      lineInputs.clear();
      busy = true;
      error = null;
    });
    try {
      final item = businessMap(await widget.session.read('/measurements/$id'));
      if (!mounted || !mayView || current != version) return;
      if (item['project_id'] != widget.projectId || item['lines'] is! List) {
        throw const ApiException(
          409,
          'Das Aufmaß gehört nicht zum gewählten Projekt.',
        );
      }
      setState(() => selected = item);
    } on ApiException catch (e) {
      if (hideOnDenied(e)) return;
      if (mounted && mayView) setState(() => error = e.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> configureLine(int index) async {
    final line = businessMap((selected!['lines'] as List)[index]);
    await showDialog<void>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Aufmaßposition übernehmen',
        readPermission: 'finance.read',
        writePermission: 'finance.write',
        initial:
            lineInputs[index] ??
            {
              'description': line['description'],
              'tax_rate': '19',
              'kind': 'service',
            },
        fields: const [
          BusinessField('description', 'Beschreibung', required: true),
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
            choices: {
              'labor': 'Lohn',
              'material': 'Material',
              'service': 'Leistung',
              'machine': 'Maschine',
            },
          ),
        ],
        onSave: (values) async {
          if (!mounted || !mayEdit)
            throw const ApiException(
              403,
              'Die Bearbeitung ist nicht mehr freigegeben.',
            );
          setState(() {
            lineInputs[index] = {...values, 'line_index': index};
            proposal = null;
            version++;
          });
        },
      ),
    );
  }

  Map<String, dynamic> inputs() => {
    'project_id': widget.projectId,
    'measurement_id': selected!['id'],
    'measurement_revision': selected!['revision'],
    'measurement_hash': selected!['content_hash'],
    'lines': [
      for (final index in lineInputs.keys.toList()..sort()) lineInputs[index],
    ],
  };

  Future<void> preview() async {
    if (!mayEdit || busy || selected == null || lineInputs.isEmpty) return;
    final current = version;
    setState(() {
      busy = true;
      error = null;
      proposal = null;
    });
    try {
      final result = businessMap(
        await widget.session.command(
          'measurement-${identityHashCode(this)}-$current',
          '/commercial/measurement-preview',
          inputs(),
        ),
      );
      if (!mounted || !mayEdit || current != version) return;
      if (result['positions'] is! List ||
          result['requires_confirmation'] != true ||
          !RegExp(r'^[a-f0-9]{64}$').hasMatch('${result['preview_hash']}')) {
        throw const ApiException(
          0,
          'Die Aufmaßvorschau konnte nicht sicher geladen werden.',
        );
      }
      setState(() => proposal = result);
    } on ApiException catch (e) {
      if (hideOnDenied(e)) return;
      if (mounted && mayView) setState(() => error = e.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Dialog(
    insetPadding: const EdgeInsets.all(16),
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 650, maxHeight: 800),
      child: !mayView
          ? _unavailableDialog(
              context,
              'Das Aufmaß ist nicht mehr verfügbar. Bitte schließen Sie die Vorschau und wählen Sie die Quelle bei Bedarf erneut aus.',
            )
          : Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 16, 8, 8),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Mengen aus Aufmaß',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                      ),
                      IconButton(
                        onPressed: () => Navigator.pop(context),
                        tooltip: 'Schließen',
                        icon: const Icon(Icons.close),
                      ),
                    ],
                  ),
                ),
                Flexible(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Wählen Sie ein Aufmaß aus diesem Projekt und legen Sie je gewünschter Zeile den Verkaufspreis fest. Das Original bleibt erhalten.',
                        ),
                        const SizedBox(height: 16),
                        if (loading) const LinearProgressIndicator(),
                        if (!loading && measurements.isEmpty && error == null)
                          const Text(
                            'In diesem Projekt sind noch keine Aufmaße vorhanden.',
                          ),
                        if (measurements.isNotEmpty)
                          DropdownButtonFormField<String>(
                            isExpanded: true,
                            decoration: const InputDecoration(
                              labelText: 'Aufmaß auswählen',
                            ),
                            items: [
                              for (final m in measurements)
                                DropdownMenuItem(
                                  value: '${m['id']}',
                                  child: Text(
                                    '${m['title']}',
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                            ],
                            onChanged: mayEdit && !busy
                                ? (id) => select(id!)
                                : null,
                          ),
                        if (selected != null) ...[
                          TextButton.icon(
                            onPressed: mayEdit && !busy
                                ? () => select('${selected!['id']}')
                                : null,
                            icon: const Icon(Icons.refresh),
                            label: const Text('Aktuelles Aufmaß laden'),
                          ),
                          const SizedBox(height: 12),
                          Text(
                            'Stand ${selected!['revision']} · ${selected!['status'] == 'signed' ? 'Unterschrieben' : 'Entwurf'}',
                          ),
                          for (final entry
                              in (selected!['lines'] as List).asMap().entries)
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              title: Text(
                                '${businessMap(entry.value)['description']}',
                              ),
                              subtitle: Text(
                                '${businessMap(entry.value)['quantity']} ${businessMap(entry.value)['unit']}${lineInputs[entry.key] == null ? ' · Noch nicht ausgewählt' : ' · ${businessMoney(lineInputs[entry.key]!['unit_price_net'])} netto'}',
                              ),
                              onTap: mayEdit && !busy
                                  ? () => configureLine(entry.key)
                                  : null,
                              trailing: lineInputs[entry.key] == null
                                  ? const Icon(Icons.add_circle_outline)
                                  : IconButton(
                                      tooltip: 'Aufmaßzeile abwählen',
                                      icon: const Icon(
                                        Icons.remove_circle_outline,
                                      ),
                                      onPressed: mayEdit && !busy
                                          ? () => setState(() {
                                              lineInputs.remove(entry.key);
                                              proposal = null;
                                              version++;
                                            })
                                          : null,
                                    ),
                            ),
                        ],
                        if (error != null) Notice(error!, error: true),
                        if (proposal != null)
                          Card(
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Mengen und Preise prüfen',
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleMedium,
                                  ),
                                  for (final p
                                      in (proposal!['positions'] as List).map(
                                        businessMap,
                                      ))
                                    Padding(
                                      padding: const EdgeInsets.symmetric(
                                        vertical: 8,
                                      ),
                                      child: Text(
                                        '${p['description']}\n${p['quantity']} ${p['unit']} × ${businessMoney(p['unit_price_net'])} netto · ${p['tax_rate']} % USt.',
                                      ),
                                    ),
                                  const Text(
                                    'Mit der Übernahme bestätigen Sie diese Mengen und Preise. Der Server prüft den Aufmaßstand beim Speichern erneut.',
                                  ),
                                ],
                              ),
                            ),
                          ),
                        const SizedBox(height: 16),
                        Wrap(
                          spacing: 12,
                          runSpacing: 12,
                          children: [
                            OutlinedButton(
                              onPressed:
                                  mayEdit && !busy && lineInputs.isNotEmpty
                                  ? preview
                                  : null,
                              child: const Text('Übernahme prüfen'),
                            ),
                            FilledButton(
                              onPressed: mayEdit && !busy && proposal != null
                                  ? () {
                                      final source = inputs()
                                        ..remove('project_id');
                                      Navigator.pop(context, <String, dynamic>{
                                        'import': {
                                          ...source,
                                          'preview_hash':
                                              proposal!['preview_hash'],
                                          'quantity_confirmation': true,
                                          'price_confirmation': true,
                                        },
                                        'positions': proposal!['positions'],
                                        'title': selected!['title'],
                                      });
                                    }
                                  : null,
                              child: const Text('Mengen und Preise übernehmen'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    ),
  );
}

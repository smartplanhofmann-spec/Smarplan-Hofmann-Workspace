import 'dart:async';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const purchaseStatuses = {
  'proposal': 'Bestellvorschlag',
  'approved': 'Vorschlag freigegeben',
  'ordered': 'Extern bestellt',
  'partially_received': 'Teilweise eingegangen',
  'received': 'Vollständig eingegangen',
};

String purchaseQuantity(Object? value, [Object? unit]) =>
    '${value ?? '—'}${unit == null || unit == '' ? '' : ' $unit'}'.replaceAll(
      '.',
      ',',
    );
String _today() => DateTime.now().toIso8601String().substring(0, 10);

bool _positive(String value) =>
    RegExp(r'^\d{1,12}(?:\.\d{1,4})?$').hasMatch(value) &&
    !RegExp(r'^0*(?:\.0*)?$').hasMatch(value);

void _validateDecimal(String value) {
  if (!RegExp(r'^\d{1,12}(?:\.\d{1,4})?$').hasMatch(value)) {
    throw const FormatException(
      'Mengen und Einstandspreise benötigen höchstens zwölf Stellen vor und vier Stellen nach dem Komma. Es wird nicht gerundet.',
    );
  }
}

class BusinessPurchasingPage extends StatefulWidget {
  const BusinessPurchasingPage({super.key, required this.session});
  final BusinessSession session;

  @override
  State<BusinessPurchasingPage> createState() => _BusinessPurchasingPageState();
}

class _BusinessPurchasingPageState extends State<BusinessPurchasingPage> {
  List<Map<String, dynamic>> orders = [], receipts = [];
  Map<String, dynamic>? order;
  String? selectedId, error;
  bool busy = false;
  int epoch = 0;
  BusinessSession? detailSession;
  BusinessSession get access => detailSession ?? widget.session;
  bool get detailReadable =>
      access.ready && access.error == null && access.can('inventory.read');

  bool get mayRead =>
      widget.session.hasModule('purchasing') &&
      widget.session.hasFeature('purchasing_receipts') &&
      widget.session.can('inventory.read');
  bool write(String additional) =>
      mayRead &&
      !busy &&
      detailReadable &&
      access.sectionEnabled('material') &&
      access.canWrite('inventory.write') &&
      (additional.isEmpty || access.canWrite(additional));

  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    clearDetailSession();
    super.dispose();
  }

  void clearDetailSession() {
    detailSession?.removeListener(detailChanged);
    detailSession?.dispose();
    detailSession = null;
  }

  void detailChanged() {
    if (mounted) setState(() {});
  }

  Future<void> loadDetailSession(String? project) async {
    if (project == widget.session.projectId) {
      clearDetailSession();
      return;
    }
    if (detailSession?.projectId != project || detailSession == null) {
      clearDetailSession();
      detailSession = BusinessSession(
        api: widget.session.api,
        projectId: project,
        projects: widget.session.projects,
      );
      detailSession!.addListener(detailChanged);
    }
    await detailSession!.load();
    if (!detailReadable) {
      throw ApiException(
        403,
        detailSession!.error ??
            'Die Bestelldetails sind für dieses Projekt nicht freigegeben.',
      );
    }
  }

  void changed() {
    if (!mounted) return;
    if (!mayRead) {
      epoch++;
      orders = [];
      receipts = [];
      order = null;
      busy = false;
      clearDetailSession();
    } else if (!widget.session.loading && detailSession != null) {
      unawaited(detailSession!.load());
    }
    setState(() {});
  }

  Future<void> load() async {
    if (!mayRead) return;
    final current = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final id = selectedId;
      if (id == null) {
        final data = businessItems(
          await widget.session.read(widget.session.query('/purchasing/orders')),
        );
        if (mounted && current == epoch && mayRead)
          setState(() => orders = data);
      } else {
        final data = businessMap(
          await widget.session.read('/purchasing/orders/$id'),
        );
        if (!mounted || current != epoch || !mayRead) return;
        await loadDetailSession(data['project_id'] as String?);
        final history = businessItems(
          await widget.session.read('/purchasing/orders/$id/receipts'),
        );
        if (mounted && current == epoch && mayRead && detailReadable)
          setState(() {
            order = data;
            receipts = history;
          });
      }
    } catch (e) {
      if (mounted && current == epoch && mayRead) {
        setState(() {
          error = '$e';
          if (e is ApiException && const [401, 403, 404].contains(e.status)) {
            order = null;
            receipts = [];
            if (selectedId == null) orders = [];
          }
        });
      }
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  Future<void> requireWrite(String additional) async {
    await access.load();
    if (!mayRead ||
        !detailReadable ||
        !access.canWrite('inventory.write') ||
        (additional.isNotEmpty && !access.canWrite(additional))) {
      throw const ApiException(
        403,
        'Die erforderliche Einkaufsberechtigung fehlt.',
      );
    }
    if (!access.sectionEnabled('material')) {
      throw const ApiException(
        423,
        'Der Materialbereich ist pausiert. Vorhandene Daten bleiben lesbar.',
      );
    }
  }

  Future<void> editProposal({bool addLine = false}) async {
    if (!write('') || !widget.session.can('finance.read')) return;
    try {
      final source = order;
      final requestSession = widget.session;
      final projectAtOpen = requestSession.projectId;
      final articleRows = businessItems(await widget.session.read('/articles'));
      if (!mounted || !write('') || !widget.session.can('finance.read')) return;
      final choices = {
        for (final item in articleRows.where(
          (item) =>
              (item['active'] == true || item['active'] == 1) &&
              const ['material', 'machine'].contains(item['kind']),
        ))
          '${item['id']}':
              '${item['code'] ?? ''} ${item['name']} · ${item['unit']}'.trim(),
      };
      if (choices.isEmpty) {
        setState(
          () => error =
              'Zuerst einen aktiven Material- oder Geräteartikel anlegen.',
        );
        return;
      }
      final lines = source == null
          ? <Map<String, dynamic>>[{}]
          : (source['items'] as List).map(businessMap).toList();
      if (addLine) lines.add({});
      final initial = <String, dynamic>{
        'supplier_name': source?['supplier_name'] ?? '',
        'project_id': source?['project_id'] ?? projectAtOpen,
        for (var i = 0; i < lines.length; i++)
          'article_$i': lines[i]['article_id'],
        for (var i = 0; i < lines.length; i++)
          'quantity_$i': lines[i]['ordered_quantity'] ?? '1',
      };
      final fields = <BusinessField>[
        const BusinessField('supplier_name', 'Lieferant', required: true),
        if (source == null && widget.session.projectId == null)
          BusinessField(
            'project_id',
            'Projekt (optional)',
            type: BusinessInput.choice,
            choices: {
              for (final project in widget.session.projects)
                '${project['id']}': '${project['name']}',
            },
          ),
        for (var i = 0; i < lines.length; i++) ...[
          BusinessField(
            'article_$i',
            'Artikel · Position ${i + 1}',
            type: BusinessInput.choice,
            required: true,
            choices: choices,
          ),
          BusinessField(
            'quantity_$i',
            'Bestellmenge · Position ${i + 1}',
            type: BusinessInput.decimal,
            required: true,
          ),
        ],
      ];
      final pendingKey =
          'purchase-proposal-${projectAtOpen ?? 'all'}-${source?['id'] ?? 'new'}-${source?['source_revision'] ?? 0}-${lines.length}';
      final saved = await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: access,
          pendingSession: requestSession,
          pendingKey: pendingKey,
          title: source == null
              ? 'Bestellvorschlag anlegen'
              : 'Bestellvorschlag bearbeiten',
          initial: initial,
          fields: fields,
          readPermission: 'finance.read',
          writePermission: 'inventory.write',
          saveLabel: 'Vorschlag speichern',
          onSave: (values) async {
            await requireWrite('');
            if (!widget.session.can('finance.read'))
              throw const ApiException(
                403,
                'Artikeldaten sind nicht freigegeben.',
              );
            final items = <Map<String, dynamic>>[];
            for (var i = 0; i < lines.length; i++) {
              final quantity = '${values['quantity_$i']}';
              _validateDecimal(quantity);
              if (!_positive(quantity))
                throw const FormatException(
                  'Bestellmengen müssen größer als null sein.',
                );
              items.add({
                'article_id': values['article_$i'],
                'quantity': quantity,
              });
            }
            final result = businessMap(
              await requestSession.command(
                pendingKey,
                '/inventory/orders${source == null ? '' : '/${source['id']}'}',
                {
                  'supplier_name': values['supplier_name'],
                  'items': items,
                  'status': 'draft',
                  'project_id': source == null
                      ? projectAtOpen ?? values['project_id']
                      : source['project_id'],
                  if (source != null) 'revision': source['source_revision'],
                },
              ),
            );
            if (mounted && mayRead) selectedId = '${result['id']}';
          },
        ),
      );
      if (mounted && saved == true) await load();
    } catch (e) {
      if (mounted && mayRead) setState(() => error = '$e');
    }
  }

  Future<void> approveProposal() async {
    final source = order;
    final requestSession = widget.session;
    if (source == null || !write('finance.approve')) return;
    final pendingKey =
        'purchase-approve-${source['id']}-${source['source_revision']}';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: access,
        pendingSession: requestSession,
        pendingKey: pendingKey,
        title: 'Bestellvorschlag freigeben',
        fields: const [
          BusinessField(
            'approved',
            'Positionen und Mengen sind geprüft',
            type: BusinessInput.toggle,
          ),
        ],
        readPermission: 'inventory.read',
        writePermission: 'finance.approve',
        saveLabel: 'Vorschlag freigeben',
        onSave: (values) async {
          await requireWrite('finance.approve');
          if (values['approved'] != true)
            throw const FormatException(
              'Bitte die Prüfung der Positionen bestätigen.',
            );
          await requestSession.command(
            pendingKey,
            '/inventory/orders/${source['id']}',
            {
              'revision': source['source_revision'],
              'project_id': source['project_id'],
              'supplier_name': source['supplier_name'],
              'status': 'approved',
              'items': [
                for (final item in (source['items'] as List).map(businessMap))
                  {
                    'article_id': item['article_id'],
                    'quantity': item['ordered_quantity'],
                  },
              ],
            },
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> confirmOrder() async {
    final source = order;
    final requestSession = widget.session;
    if (source == null || !write('finance.approve')) return;
    final pendingKey =
        'purchase-confirm-${source['id']}-${source['source_revision']}';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: access,
        pendingSession: requestSession,
        pendingKey: pendingKey,
        title: 'Extern erfolgte Bestellung dokumentieren',
        fields: const [
          BusinessField(
            'order_reference',
            'Bestellnummer / Referenz',
            required: true,
          ),
          BusinessField(
            'ordered_on',
            'Bestelldatum',
            type: BusinessInput.date,
            required: true,
          ),
          BusinessField(
            'confirmation',
            'Die Bestellung wurde außerhalb dieser Anwendung ausgelöst',
            type: BusinessInput.toggle,
          ),
        ],
        initial: {'ordered_on': _today()},
        readPermission: 'inventory.read',
        writePermission: 'finance.approve',
        saveLabel: 'Bestellung dokumentieren',
        onSave: (values) async {
          await requireWrite('finance.approve');
          if (values['confirmation'] != true)
            throw const FormatException(
              'Bitte bestätigen, dass die Bestellung bereits erfolgt ist.',
            );
          await requestSession.command(
            pendingKey,
            '/purchasing/orders/${source['id']}/confirm',
            {
              ...values,
              'source_revision': source['source_revision'],
              'expected_receipt_revision': 0,
            },
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> receive() async {
    final source = order;
    final requestSession = widget.session;
    if (source == null || !write('finance.write')) return;
    try {
      final locationRows = businessItems(
        await widget.session.read('/inventory/locations'),
      );
      if (!mounted || !write('finance.write')) return;
      final locations = {
        for (final item in locationRows.where(
          (item) => item['active'] == true || item['active'] == 1,
        ))
          '${item['id']}': '${item['name']}',
      };
      if (locations.isEmpty) {
        setState(() => error = 'Zuerst einen aktiven Lagerort anlegen.');
        return;
      }
      final lines = (source['items'] as List)
          .map(businessMap)
          .where((line) => _positive('${line['remaining_quantity']}'))
          .toList();
      final pendingKey =
          'purchase-receive-${source['id']}-${source['receipt_revision']}';
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: access,
          pendingSession: requestSession,
          pendingKey: pendingKey,
          title: 'Wareneingang buchen',
          initial: {'received_on': _today()},
          fields: [
            const BusinessField(
              'receipt_reference',
              'Lieferscheinnummer / Referenz',
              required: true,
            ),
            const BusinessField(
              'received_on',
              'Eingangsdatum',
              type: BusinessInput.date,
              required: true,
            ),
            BusinessField(
              'location_id',
              'Ziellager',
              type: BusinessInput.choice,
              choices: locations,
              required: true,
            ),
            for (final line in lines) ...[
              BusinessField(
                'quantity_${line['line_index']}',
                'Eingangsmenge · Position ${(line['line_index'] as int) + 1}',
                type: BusinessInput.decimal,
                omitIfEmpty: true,
                hint:
                    '${line['article_name']} · offen ${purchaseQuantity(line['remaining_quantity'], line['unit'])}',
              ),
              BusinessField(
                'cost_${line['line_index']}',
                'Einstand netto je Einheit · Position ${(line['line_index'] as int) + 1}',
                type: BusinessInput.decimal,
                omitIfEmpty: true,
                hint: 'EUR; einen tatsächlichen Nullpreis als 0 eingeben',
              ),
            ],
          ],
          readPermission: 'inventory.read',
          writePermission: 'finance.write',
          saveLabel: 'Wareneingang verbindlich buchen',
          onSave: (values) async {
            await requireWrite('finance.write');
            final received = <Map<String, dynamic>>[];
            for (final line in lines) {
              final index = line['line_index'];
              final quantity = values['quantity_$index'];
              final price = values['cost_$index'];
              if (quantity == null && price == null) continue;
              if (quantity is String) _validateDecimal(quantity);
              if (price is String) _validateDecimal(price);
              if (quantity is! String ||
                  !_positive(quantity) ||
                  price is! String ||
                  price.startsWith('-')) {
                throw FormatException(
                  'Für Position ${(index as int) + 1} eine positive Eingangsmenge und den bestätigten Einstandspreis angeben.',
                );
              }
              received.add({
                'line_index': index,
                'quantity': quantity,
                'unit_cost_net': price,
              });
            }
            if (received.isEmpty)
              throw const FormatException(
                'Mindestens eine eingegangene Position ausfüllen.',
              );
            await requestSession.command(
              pendingKey,
              '/purchasing/orders/${source['id']}/receipts',
              {
                'source_revision': source['source_revision'],
                'expected_receipt_revision': source['receipt_revision'],
                'receipt_reference': values['receipt_reference'],
                'received_on': values['received_on'],
                'location_id': values['location_id'],
                'lines': received,
              },
            );
          },
        ),
      );
      if (mounted) await load();
    } catch (e) {
      if (mounted && mayRead) setState(() => error = '$e');
    }
  }

  List<Widget> detail(Map<String, dynamic> value) {
    final status = value['status'];
    final confirmation = businessMap(value['confirmation']);
    return [
      Text(
        '${value['supplier_name']}',
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 8),
      Text(
        '${purchaseStatuses[status] ?? status} · ${widget.session.projects.where((project) => project['id'] == value['project_id']).firstOrNull?['name'] ?? 'Ohne Projektzuordnung'}',
      ),
      const SizedBox(height: 12),
      const Text(
        'Ein Bestellvorschlag versendet nichts. Dokumentieren Sie eine Bestellung erst, nachdem sie außerhalb dieser Anwendung erfolgt ist.',
      ),
      if (confirmation.isNotEmpty)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Text(
            'Bestellreferenz: ${confirmation['order_reference']} · ${businessDate(confirmation['ordered_on'])}',
          ),
        ),
      const SizedBox(height: 16),
      Wrap(
        spacing: 12,
        runSpacing: 12,
        children: [
          if (status == 'proposal' &&
              write('') &&
              widget.session.can('finance.read')) ...[
            OutlinedButton(
              onPressed: () => editProposal(),
              child: const Text('Vorschlag bearbeiten'),
            ),
            OutlinedButton(
              onPressed: () => editProposal(addLine: true),
              child: const Text('Position hinzufügen'),
            ),
          ],
          if (status == 'proposal' && write('finance.approve'))
            FilledButton(
              onPressed: approveProposal,
              child: const Text('Vorschlag freigeben'),
            ),
          if (status == 'approved' && write('finance.approve'))
            FilledButton(
              onPressed: confirmOrder,
              child: const Text('Externe Bestellung dokumentieren'),
            ),
          if (const ['ordered', 'partially_received'].contains(status) &&
              write('finance.write'))
            FilledButton.icon(
              onPressed: receive,
              icon: const Icon(Icons.inventory_outlined),
              label: const Text('Wareneingang buchen'),
            ),
        ],
      ),
      const SizedBox(height: 24),
      Text('Positionen', style: Theme.of(context).textTheme.titleLarge),
      for (final line in (value['items'] as List).map(businessMap))
        Card(
          child: ListTile(
            title: Text(
              '${(line['line_index'] as int) + 1}. ${line['article_name']}',
            ),
            subtitle: Text(
              '${line['article_code'] ?? ''}\nBestellt: ${purchaseQuantity(line['ordered_quantity'], line['unit'])}\n'
              'Eingegangen: ${purchaseQuantity(line['received_quantity'], line['unit'])} · Offen: ${purchaseQuantity(line['remaining_quantity'], line['unit'])}',
            ),
          ),
        ),
      const SizedBox(height: 24),
      Text('Wareneingänge', style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 8),
      if (receipts.isEmpty)
        const BusinessEmpty(
          'Noch kein Wareneingang',
          'Eingehende Teil- und Restlieferungen werden hier dauerhaft dokumentiert.',
        ),
      for (final receipt in receipts)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${receipt['receipt_reference']}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                Text(businessDate(receipt['received_on'])),
                for (final line in (receipt['lines'] as List).map(businessMap))
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Position ${(line['line_index'] as int) + 1} · ${line['article_name']}: ${purchaseQuantity(line['quantity'], line['unit'])}',
                        ),
                        if (detailReadable &&
                            access.can('finance.read') &&
                            line['unit_cost_net'] != null)
                          Text(
                            'Einstand netto: ${businessMoney(line['unit_cost_net'])} je Einheit · ${businessMoney(line['cost_net'])} gesamt',
                          ),
                        SelectableText(
                          'Lagerbuchung: ${line['movement_id']}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    if (!mayRead)
      return const BusinessEmpty(
        'Einkauf nicht freigegeben',
        'Bestellungen benötigen die passende Lagerberechtigung und einen unterstützten Server.',
      );
    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Wrap(
            spacing: 12,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                'Bestellungen und Wareneingänge',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              IconButton(
                onPressed: busy ? null : load,
                tooltip: 'Bestellungen aktualisieren',
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (selectedId != null)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: busy
                    ? null
                    : () {
                        setState(() {
                          selectedId = null;
                          clearDetailSession();
                          order = null;
                          receipts = [];
                        });
                        load();
                      },
                icon: const Icon(Icons.arrow_back),
                label: const Text('Alle Bestellungen'),
              ),
            ),
          if (!access.sectionEnabled('material'))
            const Notice(
              'Material ist fachlich deaktiviert. Die Bestell- und Lieferhistorie bleibt entsprechend Ihren Rechten lesbar.',
            ),
          if (error != null) Notice(error!, error: true),
          if (busy) const LinearProgressIndicator(),
          if (selectedId == null) ...[
            if (write('') && widget.session.can('finance.read'))
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.icon(
                  onPressed: () => editProposal(),
                  icon: const Icon(Icons.add),
                  label: const Text('Bestellvorschlag anlegen'),
                ),
              ),
            const SizedBox(height: 16),
            if (!busy && orders.isEmpty && error == null)
              const BusinessEmpty(
                'Noch keine Bestellvorschläge',
                'Erfassen Sie Lieferant, Artikel und Mengen. Freigabe, tatsächliche Bestellung und Wareneingang bleiben getrennte Schritte.',
              ),
            for (final item in orders)
              Card(
                child: ListTile(
                  title: Text('${item['supplier_name']}'),
                  subtitle: Text(
                    '${purchaseStatuses[item['status']] ?? item['status']} · ${(item['items'] as List).length} Positionen',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: busy
                      ? null
                      : () {
                          setState(() {
                            selectedId = '${item['id']}';
                            order = null;
                            receipts = [];
                          });
                          load();
                        },
                ),
              ),
          ] else if (order != null && detailReadable)
            ...detail(order!)
          else if (!busy && !detailReadable)
            const Notice(
              'Die Bestelldetails sind für dieses Projekt nicht freigegeben.',
              error: true,
            ),
        ],
      ),
    );
  }
}

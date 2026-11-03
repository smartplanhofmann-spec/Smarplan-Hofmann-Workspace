import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const inventoryCountStatus = {
  'open': 'Zählung offen',
  'counted': 'Gezählt, Freigabe offen',
  'approved': 'Bestandsdifferenz freigegeben',
  'cancelled': 'Abgebrochen',
};

String inventoryQuantity(Object? value) {
  final raw = '${value ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,12}(?:\.\d{1,4})?$').hasMatch(raw)) {
    throw const ApiException(
      400,
      'Eine nichtnegative Menge mit höchstens vier Nachkommastellen angeben.',
    );
  }
  final parts = raw.split('.');
  return '${BigInt.parse(parts.first)}.${(parts.length == 1 ? '' : parts[1]).padRight(4, '0')}';
}

Map<String, dynamic> inventoryCountValues(
  Map<String, dynamic> record,
  Map<String, dynamic> values,
) {
  return {
    'revision': record['revision'],
    'lines': [
      for (final item in businessItems(record['items']))
        (() {
          final id = businessMap(item['article'])['id'];
          final amount = inventoryQuantity(values['quantity_$id']);
          final reason = '${values['reason_$id'] ?? ''}'.trim();
          if (amount != inventoryQuantity(item['on_hand']) && reason.isEmpty) {
            throw const ApiException(400, 'Jede Bestandsdifferenz begründen.');
          }
          return {'article_id': id, 'quantity': amount, 'reason': reason};
        })(),
    ],
  };
}

Map<String, dynamic> inventoryCountRecord(
  dynamic raw, {
  String? id,
  int? revision,
  String? status,
}) {
  final value = businessMap(raw);
  if (!RegExp(r'^[a-f0-9]{32}$').hasMatch('${value['id']}') ||
      !inventoryCountStatus.containsKey(value['status']) ||
      value['revision'] is! int ||
      value['revision'] < 1 ||
      value['items'] is! List ||
      id != null && value['id'] != id ||
      revision != null && value['revision'] != revision ||
      status != null && value['status'] != status ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['history_sha256']}')) {
    throw const ApiException(
      0,
      'Die Inventurbestätigung passt nicht zum Auftrag. Der ursprüngliche Auftrag bleibt erhalten.',
    );
  }
  return value;
}

final _pendingCounts = Expando<Map<String, String>>();

class BusinessInventoryCountsPage extends StatefulWidget {
  const BusinessInventoryCountsPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessInventoryCountsPage> createState() => _InventoryCountsState();
}

class _InventoryCountsState extends State<BusinessInventoryCountsPage> {
  BusinessSession get session => widget.session;
  Map<String, String> get pending => _pendingCounts[session] ??= {};
  bool get allowed =>
      session.projectId == null &&
      session.allowed &&
      session.hasFeature('inventory_counts') &&
      session.can('inventory.read');
  bool get writable =>
      allowed &&
      session.canWrite('inventory.write') &&
      session.sectionEnabled('material');
  bool get approvable =>
      writable &&
      session.can('finance.read') &&
      session.canWrite('finance.write') &&
      session.canWrite('finance.approve');
  List<Map<String, dynamic>> counts = [], locations = [];
  Map<String, dynamic>? selected;
  int? historicalRevision;
  String? error;
  bool busy = false;
  int epoch = 0;

  @override
  void initState() {
    super.initState();
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!allowed) {
      epoch++;
      counts = [];
      locations = [];
      selected = null;
      busy = false;
    }
    if (!session.allowed) pending.clear();
    if (selected != null && !session.can('finance.read')) {
      selected = null;
    }
    setState(() {});
  }

  void guard({bool write = false, bool approve = false}) {
    if (!allowed || write && !writable || approve && !approvable) {
      throw const ApiException(
        403,
        'Die aktuelle Inventur- oder Finanzfreigabe fehlt.',
      );
    }
  }

  Future<void> load({String? id, int? revision}) async {
    if (!allowed) return;
    final captured = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await session.load();
      if (!mounted || captured != epoch || !allowed) return;
      final values = await Future.wait([
        session.read('/inventory/counts'),
        session.read('/inventory/locations'),
      ]);
      if (!mounted || captured != epoch || !allowed) return;
      counts = businessItems(values[0]);
      locations = businessItems(values[1]);
      if (id != null) {
        final record = inventoryCountRecord(
          await session.read(
            '/inventory/counts/$id${revision == null ? '' : '?revision=$revision'}',
          ),
          id: id,
        );
        if (!mounted || captured != epoch || !allowed) return;
        selected = record;
        historicalRevision = revision;
      }
    } catch (e) {
      if (mounted && captured == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && captured == epoch) setState(() => busy = false);
    }
  }

  Future<void> perform(Future<void> Function() action) async {
    try {
      await action();
    } catch (e) {
      if (mounted && allowed) setState(() => error = '$e');
    }
  }

  Future<void> edit(
    String title,
    String key,
    String path,
    List<BusinessField> fields,
    Map<String, dynamic> Function(Map<String, dynamic>) values, {
    String? id,
    int? revision,
    String? status,
    bool approval = false,
  }) async {
    guard(write: true, approve: approval);
    String? resultId;
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => BusinessEditor(
        session: session,
        title: title,
        fields: fields,
        pendingKey: key,
        readAllowed: () => allowed && (!approval || approvable),
        readPermission: 'inventory.read',
        writePermission: approval ? 'finance.approve' : 'inventory.write',
        saveLabel: title,
        onSave: (input) async {
          guard(write: true, approve: approval);
          await session.load();
          guard(write: true, approve: approval);
          pending[key] = title;
          final result = session.pending(key)
              ? await session.repeatInventoryCountCommand(key)
              : await session.command(
                  key,
                  path,
                  values(input),
                  validateResult: (result) {
                    inventoryCountRecord(
                      result,
                      id: id,
                      revision: revision,
                      status: status,
                    );
                  },
                );
          if (!session.pending(key)) pending.remove(key);
          resultId = '${businessMap(result)['id']}';
        },
      ),
    );
    if (mounted && allowed && resultId != null) await load(id: resultId);
  }

  Future<void> create([Map<String, dynamic>? correction]) async {
    guard(write: true);
    String? location = correction?['location_id'];
    if (location == null) {
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: session,
          title: 'Lagerort auswählen',
          fields: [
            BusinessField(
              'location_id',
              'Lagerort',
              type: BusinessInput.choice,
              required: true,
              choices: {
                for (final row in locations.where((l) => l['active'] == true))
                  '${row['id']}': '${row['name']}',
              },
            ),
          ],
          readPermission: 'inventory.read',
          writePermission: 'inventory.write',
          onSave: (values) async {
            location = values['location_id'];
          },
        ),
      );
    }
    if (!mounted || location == null) return;
    guard(write: true);
    final captured = epoch;
    final source = businessMap(
      await session.read('/inventory/count-sources?location_id=$location'),
    );
    if (!mounted || captured != epoch || !allowed) return;
    final items = businessItems(source['items']);
    await edit(
      correction == null ? 'Zählumfang festhalten' : 'Korrektur neu zählen',
      'inventory-count-open-$location${correction == null ? '' : '-${correction['id']}'}',
      '/inventory/counts',
      [
        BusinessField(
          'title',
          'Inventurtitel',
          required: true,
          initial: correction == null
              ? ''
              : 'Nachzählung · ${correction['title']}',
        ),
        const BusinessField(
          'counted_on',
          'Tatsächlicher Zähltag',
          type: BusinessInput.date,
          required: true,
        ),
        const BusinessField(
          'reason',
          'Anlass / Korrekturgrund',
          type: BusinessInput.multiline,
          required: true,
        ),
        if (correction == null)
          BusinessField(
            'article_ids',
            'Zu zählende Artikel',
            type: BusinessInput.multiple,
            required: true,
            choices: {
              for (final item in items)
                '${item['article']['id']}':
                    '${item['article']['code']} · ${item['article']['name']} (${item['article']['unit']})',
            },
            hint: 'Dieser Auftrag umfasst genau die ausgewählten Artikel, höchstens 200.',
          ),
      ],
      (input) => {
        ...input,
        'location_id': location,
        'correction_of': correction?['id'],
        'article_ids': correction == null
            ? input['article_ids']
            : businessItems(correction['items'])
                  .map((i) => i['article']['id'])
                  .toList(),
      },
      revision: 1,
      status: 'open',
    );
  }

  Future<void> count(Map<String, dynamic> record) => edit(
    'Zählung dokumentieren',
    'inventory-count-count-${record['id']}',
    '/inventory/counts/${record['id']}/count',
    [
      for (final item in businessItems(record['items'])) ...[
        BusinessField(
          'quantity_${item['article']['id']}',
          'Gezählte Menge · ${item['article']['name']}',
          required: true,
          initial: item['counted_quantity'],
          hint:
              'Einheit ${item['article']['unit']} · auch 0 ausdrücklich eingeben',
        ),
        BusinessField(
          'reason_${item['article']['id']}',
          'Differenzgrund · ${item['article']['name']}',
          initial: item['reason'],
        ),
      ],
    ],
    (input) => inventoryCountValues(record, input),
    id: record['id'],
    revision: record['revision'] + 1,
    status: 'counted',
  );
  Future<void> cancel(Map<String, dynamic> record) => edit(
    'Abbruch dokumentieren',
    'inventory-count-cancel-${record['id']}',
    '/inventory/counts/${record['id']}/cancel',
    [
      const BusinessField(
        'reason',
        'Abbruchgrund',
        required: true,
        type: BusinessInput.multiline,
      ),
    ],
    (input) => {'revision': record['revision'], ...input},
    id: record['id'],
    revision: record['revision'] + 1,
    status: 'cancelled',
  );
  Future<void> approve(Map<String, dynamic> record) async {
    guard(write: true, approve: true);
    final needed = businessItems(record['items'])
        .where(
          (item) =>
              inventoryQuantity(item['on_hand']) == '0.0000' &&
              inventoryQuantity(item['counted_quantity']) != '0.0000',
        )
        .toList();
    Map<String, dynamic>? prices;
    if (needed.isNotEmpty) {
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: session,
          title: 'Mehrbestand ohne bisherigen Bestand bewerten',
          fields: [
            for (final item in needed)
              BusinessField(
                '${item['article']['id']}',
                'Einstandspreis netto · ${item['article']['name']}',
                required: true,
                hint: 'Auch tatsächlichen Nullpreis ausdrücklich eintragen.',
              ),
          ],
          readPermission: 'finance.read',
          writePermission: 'finance.approve',
          onSave: (values) async {
            prices = {
              for (final item in needed)
                '${item['article']['id']}': inventoryQuantity(
                  values['${item['article']['id']}'],
                ),
            };
          },
        ),
      );
      if (!mounted || prices == null) return;
    }
    prices ??= {};
    final captured = epoch;
    guard(write: true, approve: true);
    final generation = session.generation;
    final preview = businessMap(
      await session.api.call(
        session.path('/inventory/counts/${record['id']}/preview'),
        {'revision': record['revision'], 'zero_stock_unit_costs': prices},
      ),
    );
    if (!mounted || captured != epoch || session.generation != generation)
      return;
    guard(write: true, approve: true);
    if (preview['id'] != record['id'] ||
        preview['revision'] != record['revision'] ||
        preview['project_cost_effect'] != 'none') {
      throw const ApiException(
        0,
        'Die Bewertung gehört nicht zu dieser Inventurfassung.',
      );
    }
    final valuation = businessItems(preview['items'])
        .map((item) {
          final source = businessItems(record['items'])
              .firstWhere((i) => i['article']['id'] == item['article_id']);
          return '${source['article']['name']}: ${item['quantity_delta']} ${source['article']['unit']} · ${businessMoney(item['value_delta_net'])} netto';
        })
        .join('\n');
    await edit(
      'Differenzen verbindlich buchen',
      'inventory-count-approve-${record['id']}',
      '/inventory/counts/${record['id']}/approve',
      [
        BusinessField(
          'confirmed',
          '$valuation\n\nIch bestätige Mengen, Differenzgründe und Lagerbewertung.',
          type: BusinessInput.toggle,
          required: true,
        ),
      ],
      (input) => {
        'revision': record['revision'],
        'zero_stock_unit_costs': prices,
        'confirmed': input['confirmed'],
      },
      id: record['id'],
      revision: record['revision'] + 1,
      status: 'approved',
      approval: true,
    );
  }

  Future<void> history(Map<String, dynamic> record) async {
    final captured = epoch;
    final values = businessItems(
      await session.read('/inventory/counts/${record['id']}/history'),
    );
    if (!mounted || captured != epoch || !allowed) return;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Inventurhistorie'),
        content: ListenableBuilder(
          listenable: session,
          builder: (_, child) =>
              !allowed ? const Text('Inventurberechtigung entzogen.') : child!,
          child: SizedBox(
            width: 520,
            child: ListView(
              shrinkWrap: true,
              children: [
                for (final item in values)
                  ListTile(
                    title: Text(
                      'Fassung ${item['revision']} · ${inventoryCountStatus[item['status']]}',
                    ),
                    subtitle: Text(
                      businessDate(item['updated_at'], time: true),
                    ),
                    onTap: () {
                      Navigator.pop(dialogContext);
                      load(id: record['id'], revision: item['revision']);
                    },
                  ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Schließen'),
          ),
        ],
      ),
    );
  }

  Future<void> retry(String key) async {
    guard(write: true);
    final value = businessMap(await session.repeatInventoryCountCommand(key));
    if (!session.pending(key)) pending.remove(key);
    if (mounted && allowed) await load(id: '${value['id']}');
  }

  @override
  Widget build(BuildContext context) {
    if (!allowed)
      return const Scaffold(
        body: Center(
          child: Text('Inventur für diesen Zugang nicht verfügbar.'),
        ),
      );
    final record = selected;
    final editable =
        record != null &&
        historicalRevision == null &&
        writable &&
        ['open', 'counted'].contains(record['status']);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Inventur'),
        actions: [
          IconButton(
            tooltip: 'Aktualisieren',
            onPressed: busy
                ? null
                : () => load(id: record?['id'], revision: historicalRevision),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Notice(
            'Gezählte Mengen werden zunächst dokumentiert. Erst die ausdrückliche Finanzfreigabe bucht Bestands- und Wertdifferenzen. Projektkosten bleiben unverändert.',
          ),
          if (busy) const LinearProgressIndicator(),
          if (error != null) Notice(error!, error: true),
          for (final entry in pending.entries.where(
            (entry) => session.pending(entry.key),
          ))
            Card(
              child: ListTile(
                title: Text('Antwort offen · ${entry.value}'),
                subtitle: const Text(
                  'Den ursprünglichen Auftrag nach frischer Rechteprüfung unverändert wiederholen.',
                ),
                trailing: TextButton(
                  onPressed: () => perform(() => retry(entry.key)),
                  child: const Text('Antwort prüfen'),
                ),
              ),
            ),
          if (writable)
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton(
                onPressed: busy ? null : () => perform(create),
                child: const Text('Neue Inventur'),
              ),
            ),
          for (final item in counts)
            Card(
              child: ListTile(
                title: Text('${item['title']}'),
                subtitle: Text(
                  '${item['location_name']} · ${inventoryCountStatus[item['status']]} · ${businessDate(item['counted_on'])}',
                ),
                onTap: () => load(id: item['id']),
              ),
            ),
          if (!busy && counts.isEmpty)
            const BusinessEmpty(
              'Noch keine Inventur',
              'Eine physische Zählung beginnt mit Lagerort und Artikelauswahl.',
            ),
          if (record != null) ...[
            const Divider(height: 36),
            Text(
              '${record['title']} · Fassung ${record['revision']}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(
              '${record['location_name']} · ${inventoryCountStatus[record['status']]}',
            ),
            Text('${record['reason']}'),
            if (historicalRevision != null)
              const Notice(
                'Historische Fassung. Spätere Fassungen bleiben eigenständig erhalten.',
              ),
            if (record['basis_current'] == false)
              const Notice(
                'Lagerstand, Reservierung oder Artikel wurde inzwischen geändert. Diesen Auftrag abbrechen und neu zählen.',
                error: true,
              ),
            for (final item in businessItems(record['items']))
              Card(
                child: ListTile(
                  title: Text(
                    '${item['article']['name']} · ${item['article']['unit']}',
                  ),
                  subtitle: Text(
                    'Sollbestand ${item['on_hand']} · reserviert ${item['reserved']}\nGezählt ${item['counted_quantity'] ?? 'noch offen'} · Differenz ${item['difference'] ?? 'noch offen'}\n${item['reason']}${item['adjustment_value_net'] == null ? '' : '\nWertänderung netto: ${businessMoney(item['adjustment_value_net'])}'}',
                  ),
                ),
              ),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                if (editable && record['basis_current'] == true)
                  FilledButton(
                    onPressed: () => perform(() => count(record)),
                    child: Text(
                      record['status'] == 'counted'
                          ? 'Zählung korrigieren'
                          : 'Mengen zählen',
                    ),
                  ),
                if (editable &&
                    record['basis_current'] == true &&
                    record['status'] == 'counted' &&
                    approvable)
                  FilledButton(
                    onPressed: () => perform(() => approve(record)),
                    child: const Text('Differenzen prüfen und freigeben'),
                  ),
                if (editable)
                  OutlinedButton(
                    onPressed: () => perform(() => cancel(record)),
                    child: const Text('Zählauftrag abbrechen'),
                  ),
                if (record['status'] == 'approved' &&
                    historicalRevision == null &&
                    writable)
                  OutlinedButton(
                    onPressed: () => perform(() => create(record)),
                    child: const Text('Neue Korrektur zählen'),
                  ),
                OutlinedButton(
                  onPressed: () => perform(() => history(record)),
                  child: const Text('Fassungen anzeigen'),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

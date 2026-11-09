import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const communicationKinds = {
  'inquiry': 'Anfragen',
  'sales': 'Vertrieb und Aktivitäten',
  'service': 'Kundenservice',
  'document': 'Belegstände',
  'delivery': 'Belegversand',
  'project_note': 'Projektnotizen',
};
const _provenance = {
  'inquiry': ['received_inquiry', 'recorded_inquiry'],
  'sales': ['canonical_record', 'manual_activity'],
  'service': ['canonical_record', 'manual_activity'],
  'document': ['current_document_revision'],
  'delivery': ['mail_outbox', 'mail_receipt'],
  'project_note': ['internal_project_note'],
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _bad() => throw const ApiException(
  502,
  'Der Kommunikationsverlauf stimmt nicht mit seiner Quelle, Auswahl oder Fortsetzung überein.',
);
List<String> _strings(dynamic value) {
  if (value is! List || value.any((v) => v is! String)) _bad();
  return List<String>.from(value);
}

bool _keys(dynamic value, List<String> expected) =>
    value is Map &&
    value.length == expected.length &&
    value.keys.toSet().containsAll(expected);
bool _nullableId(dynamic value) =>
    value == null || value is String && _id.hasMatch(value);
bool _day(dynamic value) {
  if (value is! String || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value))
    return false;
  final parsed = DateTime.tryParse(value);
  return parsed != null && parsed.toIso8601String().substring(0, 10) == value;
}

bool _stamp(dynamic value) {
  if (value is! String ||
      !RegExp(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$').hasMatch(value))
    return false;
  final parsed = DateTime.tryParse(value);
  return parsed != null &&
      parsed.toUtc().toIso8601String().substring(0, 19) ==
          value.substring(0, 19);
}

String _order(Map<String, dynamic> value) =>
    '${value['occurred_at']}${value['precision'] == 'day' ? 'T00:00:00+00:00' : ''}|${value['key']}';

Map<String, dynamic> communicationHistoryPage(
  dynamic raw,
  Map<String, dynamic> scope, {
  Map<String, dynamic>? previous,
}) {
  if (!_keys(raw, [
    'schema_version',
    'scope',
    'snapshot_sha256',
    'customer',
    'project',
    'items',
    'next_cursor',
    'has_more',
    'page_size',
    'limitations',
  ]))
    _bad();
  final value = businessMap(raw), s = businessMap(value['scope']);
  if (value['schema_version'] != 1 ||
      !_hash.hasMatch('${value['snapshot_sha256'] ?? ''}') ||
      !_keys(s, ['customer_id', 'project_id', 'kind', 'q', 'from', 'to']) ||
      !_nullableId(s['customer_id']) ||
      !_nullableId(s['project_id']) ||
      s['customer_id'] == null && s['project_id'] == null ||
      s['project_id'] != scope['project_id'] ||
      scope['customer_id'] != null &&
          s['customer_id'] != scope['customer_id'] ||
      s['kind'] != scope['kind'] ||
      s['q'] != '${scope['q'] ?? ''}'.trim() ||
      s['from'] != scope['from'] ||
      s['to'] != scope['to'])
    _bad();
  for (final name in ['customer', 'project']) {
    final id = s['${name}_id'], record = value[name];
    if (id == null
        ? record != null
        : !_keys(record, ['id', 'name']) ||
              record['id'] != id ||
              record['name'] is! String ||
              (record['name'] as String).isEmpty)
      _bad();
  }
  final items = value['items'],
      size = value['page_size'],
      cursor = value['next_cursor'];
  if (items is! List ||
      size is! int ||
      size != int.tryParse('${scope['limit'] ?? 50}') ||
      size < 1 ||
      size > 100 ||
      items.length > size ||
      value['has_more'] is! bool ||
      value['has_more'] != (cursor != null) ||
      cursor != null &&
          (cursor is! String ||
              !RegExp(r'^[A-Za-z0-9_-]{1,1400}$').hasMatch(cursor)) ||
      value['limitations'] is! List ||
      (value['limitations'] as List).any((v) => v is! String))
    _bad();
  if (previous != null &&
      ([
            'customer_id',
            'project_id',
            'kind',
            'q',
            'from',
            'to',
          ].any((key) => previous['scope'][key] != s[key]) ||
          previous['snapshot_sha256'] != value['snapshot_sha256'] ||
          previous['has_more'] != true))
    _bad();
  final all = <Map<String, dynamic>>[
        ...businessItems(previous?['items'] ?? []),
      ],
      seen = all.map((v) => v['key']).toSet();
  for (final raw in items) {
    if (!_keys(raw, [
      'key',
      'kind',
      'source_id',
      'source_revision',
      'source_sha256',
      'project_ids',
      'title',
      'text',
      'occurred_at',
      'precision',
      'recorded_at',
      'status',
      'provenance',
      'supersedes_key',
      'superseded',
      'accepted_by_server',
      'recipient_delivery_confirmed',
    ]))
      _bad();
    final item = businessMap(raw),
        kind = item['kind'],
        provenance = item['provenance'],
        revision = item['source_revision'],
        projects = item['project_ids'];
    if (!communicationKinds.containsKey(kind) ||
        !_provenance[kind]!.contains(provenance) ||
        !_id.hasMatch('${item['source_id'] ?? ''}') ||
        revision is! int ||
        revision < 0 ||
        revision == 0 && provenance != 'mail_outbox' ||
        item['key'] != '$kind:$provenance:${item['source_id']}:$revision' ||
        seen.contains(item['key']) ||
        !_hash.hasMatch('${item['source_sha256'] ?? ''}') ||
        projects is! List ||
        projects.toSet().length != projects.length ||
        projects.any((v) => v is! String || !_id.hasMatch(v)) ||
        s['project_id'] != null && !projects.contains(s['project_id']) ||
        item['title'] is! String ||
        (item['title'] as String).runes.length > 500 ||
        item['text'] is! String ||
        (item['text'] as String).runes.length > 40000 ||
        item['status'] is! String ||
        !['day', 'second'].contains(item['precision']) ||
        !(item['precision'] == 'day'
            ? _day(item['occurred_at'])
            : _stamp(item['occurred_at'])) ||
        !_stamp(item['recorded_at']) ||
        item['superseded'] is! bool ||
        item['supersedes_key'] != null &&
            (item['supersedes_key'] is! String ||
                !(item['supersedes_key'] as String).startsWith(
                  '$kind:manual_activity:',
                )) ||
        item['accepted_by_server'] is! bool ||
        item['accepted_by_server'] !=
            (kind == 'delivery' && item['status'] == 'accepted') ||
        item['recipient_delivery_confirmed'] != false)
      _bad();
    if (all.isNotEmpty && _order(all.last).compareTo(_order(item)) <= 0) _bad();
    seen.add(item['key']);
    all.add(item);
  }
  if (value['has_more'] == true && items.isEmpty) _bad();
  return {...value, 'items': all};
}

String communicationStatus(Map<String, dynamic> item) {
  const delivery = {
    'pending': 'Vorbereitet',
    'sending': 'Versand läuft',
    'accepted': 'Vom Versandserver angenommen',
    'failed': 'Versand fehlgeschlagen',
    'unknown': 'Versand ungeklärt',
    'not_sent': 'Nicht versendet bestätigt',
  };
  const common = {
    'recorded_activity': 'Protokollierte Aktivität',
    'recorded_note': 'Interne Notiz',
    'draft': 'Entwurf',
    'final': 'Abgeschlossen',
    'new': 'Neu',
    'qualified': 'Qualifiziert',
    'proposal': 'Angebotsphase',
    'negotiation': 'Verhandlung',
    'won': 'Gewonnen',
    'lost': 'Verloren',
    'open': 'Offen',
    'triaged': 'Geprüft',
    'planned': 'Geplant',
    'in_progress': 'In Bearbeitung',
    'waiting_customer': 'Rückmeldung des Kunden offen',
    'waiting_supplier': 'Rückmeldung des Lieferanten offen',
    'resolved': 'Gelöst',
    'closed': 'Abgeschlossen',
    'cancelled': 'Abgebrochen',
    'callback': 'Rückruf',
    'review': 'In Prüfung',
    'offer': 'Angebot',
    'awaiting_acceptance': 'Zusage offen',
    'accepted': 'Zusage vermerkt',
    'declined': 'Abgelehnt',
    'converted': 'In Projekt übernommen',
  };
  return (item['kind'] == 'delivery' ? delivery : common)[item['status']] ??
      '${item['status']}';
}

class BusinessCommunicationHistoryPage extends StatefulWidget {
  const BusinessCommunicationHistoryPage({
    super.key,
    required this.session,
    this.customerId,
    this.projectId,
    this.active = true,
  });
  final BusinessSession session;
  final String? customerId, projectId;
  final bool active;
  @override
  State<BusinessCommunicationHistoryPage> createState() =>
      _CommunicationState();
}

class _CommunicationState extends State<BusinessCommunicationHistoryPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  bool get allowed =>
      widget.active &&
      session.hasFeature('communication_history') &&
      session.hasModule('sales') &&
      session.can('contacts.read');
  String? get projectId =>
      widget.projectId ??
      (widget.customerId == null ? session.projectId : null);
  final query = TextEditingController();
  String? kind, from, to, error;
  Map<String, dynamic>? page;
  int epoch = 0;
  bool loading = false;
  late String signature;
  String rights() => jsonEncode([
    session.allowed,
    session.generation,
    session.permissions.toList()..sort(),
    session.features.toList()..sort(),
    session.capabilities.toList()..sort(),
  ]);
  @override
  void initState() {
    super.initState();
    signature = rights();
    session.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
    if (widget.active) load();
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    query.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant BusinessCommunicationHistoryPage old) {
    super.didUpdateWidget(old);
    if (old.session != session ||
        old.customerId != widget.customerId ||
        old.projectId != widget.projectId ||
        old.active != widget.active) {
      old.session.removeListener(changed);
      session.addListener(changed);
      clear();
      signature = rights();
      if (widget.active) load();
    }
  }

  void clear() {
    epoch++;
    page = null;
    loading = false;
    query.clear();
    kind = from = to = null;
  }

  void changed() {
    if (!mounted) return;
    final next = rights();
    if (!allowed || next != signature) {
      clear();
      signature = next;
    }
    setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed && mounted)
      setState(() {
        clear();
        error =
            'Der private Verlauf wurde ausgeblendet. Zum Fortsetzen neu laden.';
      });
  }

  Future<String> fresh() async {
    if (!allowed)
      throw const ApiException(
        403,
        'Der aktuelle Zugang zum Kommunikationsverlauf fehlt.',
      );
    final caps = businessMap(
      await session.read(
        '/capabilities${projectId == null ? '' : '?${Uri(queryParameters: {'project_id': projectId}).query}'}',
      ),
    );
    if (!_strings(caps['permissions']).contains('contacts.read') ||
        !_strings(caps['features']).contains('communication_history') ||
        !_strings(caps['capabilities']).contains('business_sales'))
      throw const ApiException(
        403,
        'Die aktuelle Lesefreigabe für den Kommunikationsverlauf fehlt.',
      );
    return jsonEncode([
      caps['generation'],
      _strings(caps['permissions'])..sort(),
      _strings(caps['features'])..sort(),
      _strings(caps['capabilities'])..sort(),
    ]);
  }

  Future<void> load({bool next = false}) async {
    if (loading) return;
    final ticket = ++epoch, owner = session, previous = next ? page : null;
    final parameters = <String, String>{
      if (widget.customerId != null) 'customer_id': widget.customerId!,
      if (projectId != null) 'project_id': projectId!,
      if (query.text.isNotEmpty) 'q': query.text,
      if (kind != null) 'kind': kind!,
      if (from != null) 'from': from!,
      if (to != null) 'to': to!,
      'limit': '50',
      if (previous != null) 'cursor': previous['next_cursor'] as String,
    };
    setState(() {
      loading = true;
      error = null;
      page = null;
    });
    try {
      final before = await fresh(),
          result = await owner.read(
            '/sales/communication-history?${Uri(queryParameters: parameters).query}',
          ),
          after = await fresh();
      if (!mounted || ticket != epoch || owner != session) return;
      if (before != after)
        throw const ApiException(
          409,
          'Die Leserechte wurden während des Abrufs geändert. Bitte neu laden.',
        );
      final checked = communicationHistoryPage(
        result,
        parameters,
        previous: previous,
      );
      setState(() => page = checked);
    } catch (e) {
      if (mounted && ticket == epoch && owner == session)
        setState(() {
          page = null;
          error = '$e';
        });
    } finally {
      if (mounted && ticket == epoch) setState(() => loading = false);
    }
  }

  Future<void> pickDate(bool start) async {
    final selected = await showDatePicker(
      context: context,
      initialDate:
          DateTime.tryParse((start ? from : to) ?? '') ?? DateTime.now(),
      firstDate: DateTime(1900),
      lastDate: DateTime(2200),
    );
    if (selected != null && mounted)
      setState(() {
        if (start)
          from = selected.toIso8601String().substring(0, 10);
        else
          to = selected.toIso8601String().substring(0, 10);
      });
  }

  String dateText(String value, {bool day = false, bool activity = true}) {
    if (day)
      return '${value.substring(8, 10)}.${value.substring(5, 7)}.${value.substring(0, 4)}${activity ? ' · ohne belegte Uhrzeit' : ''}';
    return businessDate(value, time: true);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Kommunikationsverlauf'),
      actions: [
        if (allowed)
          IconButton(
            tooltip: 'Verlauf neu laden',
            onPressed: loading ? null : () => load(),
            icon: const Icon(Icons.refresh),
          ),
      ],
    ),
    body: !allowed
        ? const Center(child: Text('Der Zugang ist nicht mehr verfügbar.'))
        : ListView(
            padding: const EdgeInsets.all(20),
            children: [
              TextField(
                controller: query,
                decoration: const InputDecoration(
                  labelText: 'Kommunikationsverlauf durchsuchen',
                ),
                maxLength: 200,
                onSubmitted: (_) => load(),
              ),
              DropdownButtonFormField<String>(
                isExpanded: true,
                key: ValueKey(kind),
                initialValue: kind ?? '',
                decoration: const InputDecoration(labelText: 'Verlaufsquelle'),
                items: [
                  const DropdownMenuItem(
                    value: '',
                    child: Text('Alle Quellen'),
                  ),
                  for (final entry in communicationKinds.entries)
                    DropdownMenuItem(
                      value: entry.key,
                      child: Text(entry.value),
                    ),
                ],
                onChanged: loading
                    ? null
                    : (value) =>
                          setState(() => kind = value == '' ? null : value),
              ),
              Wrap(
                spacing: 8,
                children: [
                  TextButton(
                    onPressed: loading ? null : () => pickDate(true),
                    child: Text(
                      from == null
                          ? 'Verlauf ab'
                          : dateText(from!, day: true, activity: false),
                    ),
                  ),
                  TextButton(
                    onPressed: loading ? null : () => pickDate(false),
                    child: Text(
                      to == null
                          ? 'Verlauf bis'
                          : dateText(to!, day: true, activity: false),
                    ),
                  ),
                  if (from != null || to != null)
                    TextButton(
                      onPressed: () => setState(() => from = to = null),
                      child: const Text('Zeitraum entfernen'),
                    ),
                ],
              ),
              FilledButton(
                onPressed: loading ? null : () => load(),
                child: const Text('Verlauf filtern'),
              ),
              if (loading) const LinearProgressIndicator(),
              if (error != null) Notice(error!, error: true),
              if (page != null) ...[
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    page!['project'] != null
                        ? 'Projekt: ${page!['project']['name']}'
                        : 'Kunde: ${page!['customer']['name']}',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Hinweise zu Quellen und Nachweisen'),
                  children: [
                    for (final limitation in _strings(page!['limitations']))
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Text(limitation),
                      ),
                  ],
                ),
                if ((page!['items'] as List).isEmpty)
                  const Notice(
                    'Keine freigegebenen Einträge für diese Auswahl vorhanden.',
                  ),
                for (final item in businessItems(page!['items']))
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item['title'],
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          Text(
                            '${communicationKinds[item['kind']]} · ${dateText(item['occurred_at'], day: item['precision'] == 'day')}',
                          ),
                          Text(communicationStatus(item)),
                          if (item['provenance'] == 'manual_activity')
                            const Text(
                              'Manuell protokolliert; kein Versandnachweis.',
                            ),
                          if (item['superseded'] == true)
                            const Notice(
                              'Dieser Originaleintrag wurde korrigiert. Die spätere Korrektur bleibt ein eigener Nachweis.',
                            ),
                          if ((item['text'] as String).isNotEmpty)
                            SelectableText(item['text']),
                          if (item['kind'] == 'delivery')
                            const Text(
                              'Zustellung und Lesen sind nicht bestätigt.',
                            ),
                          Text(
                            'Erfasst: ${businessDate(item['recorded_at'], time: true)}',
                          ),
                        ],
                      ),
                    ),
                  ),
                if (page!['has_more'] == true)
                  OutlinedButton(
                    onPressed: loading ? null : () => load(next: true),
                    child: const Text('Weitere Einträge laden'),
                  ),
              ],
            ],
          ),
  );
}

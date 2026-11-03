import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting.dart'
    show accountingAmount, businessAccountingReadable;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

bool businessRefundOriginsReadable(BusinessSession session) =>
    businessAccountingReadable(session) &&
    session.hasFeature('accounting_refund_origins') &&
    session.hasModule('accounting_refunds');

const _blocked = {
  'not_customer_refund': 'Dieser Geldfluss ist keine Kundenerstattung.',
  'source_customer_unresolved':
      'Die Kundenbindung der ursprünglichen Rechnungen ist noch ungeklärt.',
  'unsupported_document': 'Dieser Beleg benötigt eine gesonderte Prüfung.',
  'unallocated':
      'Der verbleibende Erstattungsbetrag ist noch keiner Rechnung zugeordnet.',
  'fully_documented':
      'Die Ursprünge dieser Erstattung sind vollständig dokumentiert.',
};
BigInt _cents(Object? value) => BigInt.parse('$value'.replaceAll('.', ''));
String _lotKey(Map<String, dynamic> origin) =>
    '${origin['entry_id']}:${origin['group_id']}';
String _blockedText(Object? reason) =>
    _blocked[reason] ?? 'Dieser Erstattungsanteil benötigt eine Klärung.';

class BusinessRefundOriginsPage extends StatefulWidget {
  const BusinessRefundOriginsPage({
    super.key,
    required this.session,
    required this.eventId,
  });
  final BusinessSession session;
  final String eventId;
  @override
  State<BusinessRefundOriginsPage> createState() =>
      _BusinessRefundOriginsPageState();
}

class _BusinessRefundOriginsPageState extends State<BusinessRefundOriginsPage> {
  Map<String, dynamic>? state, selected, preview, confirmBody;
  List<Map<String, dynamic>> portions = [], history = [], origins = [];
  final originInputs = <String, TextEditingController>{};
  final reason = TextEditingController();
  final scroll = ScrollController();
  bool loading = false, busy = false, denied = false, continuing = false;
  int epoch = 0;
  int? nextPortions, nextHistory, nextOrigins;
  String? error, message;
  String get path => '/accounting/refunds/events/${widget.eventId}';
  String get key => 'accounting-refunds-${widget.eventId}';
  bool get mayRead => businessRefundOriginsReadable(widget.session) && !denied;
  bool get writeRights =>
      mayRead &&
      widget.session.canWrite('accounting.prepare') &&
      widget.session.canWrite('finance.write') &&
      widget.session.sectionEnabled('finance');
  bool get mayWrite =>
      writeRights &&
      state?['writes_allowed'] == true &&
      widget.session.error == null &&
      !loading &&
      !busy;
  bool get pending => widget.session.pending(key);

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
    for (final input in originInputs.values) {
      input.dispose();
    }
    reason.dispose();
    scroll.dispose();
    super.dispose();
  }

  void clear() {
    epoch++;
    state = selected = preview = confirmBody = null;
    portions = [];
    history = [];
    nextPortions = nextHistory = nextOrigins = null;
    origins = [];
    for (final input in originInputs.values) {
      input.clear();
    }
    reason.clear();
    continuing = loading = busy = false;
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!businessRefundOriginsReadable(widget.session))
        clear();
      else if (!writeRights)
        portions = [];
    });
  }

  void failure(Object e) {
    if (!mounted) return;
    setState(() {
      if (e is ApiException && [401, 403, 404].contains(e.status)) {
        clear();
        denied = true;
      }
      error = e is ApiException
          ? e.message
          : e is FormatException
          ? e.message
          : 'Die Erstattungsursprünge konnten nicht geladen werden.';
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) scroll.jumpTo(0);
    });
  }

  Future<Map<String, dynamic>?> authorizedPendingPreview() async {
    if (widget.session.hasFeature('accounting_refund_origins_v2') &&
        widget.session.hasModule('accounting_refunds_v2'))
      return null;
    final body = widget.session.pendingCommandValues(
      key,
      path: '$path/confirm',
    );
    if (body == null) return null;
    final saved = widget.session.pendingEditorValues(key);
    final proposal = saved?['preview'] is Map
        ? businessMap(saved!['preview'])
        : null;
    if (proposal == null) return null;
    final requested = businessItems(body['origins']).map(_lotKey).toSet();
    final lines = businessItems(proposal['lines']);
    if (lines.isEmpty ||
        lines.map(_lotKey).toSet().difference(requested).isNotEmpty ||
        requested.difference(lines.map(_lotKey).toSet()).isNotEmpty)
      return null;
    await authorizeOrigins(lines);
    return proposal;
  }

  // A document alone does not prove access to the whole incoming payment.
  // Recheck every original CashEvent, including its later project bindings.
  Future<void> authorizeOrigins(List<Map<String, dynamic>> values) async {
    final ids = values.map((v) => v['origin_event_id']).toSet();
    for (final id in ids) {
      if (id is! String || !RegExp(r'^[a-f0-9]{32}$').hasMatch(id))
        throw const ApiException(
          409,
          'Der Ursprungsnachweis muss neu geladen werden.',
        );
      await widget.session.read('/accounting/events/$id');
    }
  }

  Future<void> load() async {
    if (!businessRefundOriginsReadable(widget.session)) return;
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final fresh = businessMap(await widget.session.read(path));
      final openingPending = widget.session.pendingCommandValues(
        key,
        path: '$path/confirm',
      );
      final saved = await authorizedPendingPreview();
      final result = await Future.wait([
        widget.session.read('$path/history?limit=50&offset=0'),
        if (businessRefundOriginsReadable(widget.session) &&
            widget.session.canWrite('accounting.prepare') &&
            widget.session.canWrite('finance.write') &&
            widget.session.sectionEnabled('finance') &&
            fresh['writes_allowed'] == true &&
            fresh['eligible'] == true)
          widget.session.read('$path/portions?limit=50&offset=0'),
      ]);
      if (!mounted ||
          current != epoch ||
          !businessRefundOriginsReadable(widget.session))
        return;
      final currentPending = widget.session.pendingCommandValues(
        key,
        path: '$path/confirm',
      );
      if (jsonEncode(openingPending) != jsonEncode(currentPending)) {
        // A previously opened page may have received its acknowledgement while
        // target/history reads were in flight. Refresh its committed result.
        await load();
        return;
      }
      setState(() {
        denied = false;
        state = fresh;
        history = businessItems(result[0]);
        nextHistory = businessMap(result[0])['next_offset'] as int?;
        portions = result.length == 2 ? businessItems(result[1]) : [];
        nextPortions = result.length == 2
            ? businessMap(result[1])['next_offset'] as int?
            : null;
        selected = null;
        origins = [];
        nextOrigins = null;
        preview = saved;
        confirmBody = currentPending;
        continuing = confirmBody != null;
        for (final input in originInputs.values) {
          input.clear();
        }
        reason.clear();
      });
    } catch (e) {
      if (mounted && current == epoch) failure(e);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> more({required bool historyPage}) async {
    final offset = historyPage ? nextHistory : nextPortions;
    if (offset == null ||
        busy ||
        loading ||
        !mayRead ||
        (!historyPage && !mayWrite))
      return;
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = businessMap(
        await widget.session.read(
          '$path/${historyPage ? 'history' : 'portions'}?limit=50&offset=$offset',
        ),
      );
      if (!mounted || current != epoch || !mayRead) return;
      setState(() {
        if (historyPage) {
          history = [...history, ...businessItems(result)];
          nextHistory = result['next_offset'] as int?;
        } else {
          portions = [...portions, ...businessItems(result)];
          nextPortions = result['next_offset'] as int?;
        }
      });
    } catch (e) {
      if (mounted && current == epoch) failure(e);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> choose(Map<String, dynamic> portion) async {
    if (!mayWrite || pending) return;
    for (final input in originInputs.values) {
      input.clear();
    }
    setState(() {
      selected = portion;
      origins = [];
      nextOrigins = null;
      reason.clear();
      error = null;
    });
    await loadOrigins();
  }

  Future<void> loadOrigins({bool more = false}) async {
    if (!mayWrite ||
        selected == null ||
        pending ||
        (more && nextOrigins == null))
      return;
    final current = ++epoch,
        portion = selected!,
        offset = more ? nextOrigins! : 0;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = businessMap(
        await widget.session.read(
          '$path/origins?portion_id=${portion['portion_id']}&limit=50&offset=$offset',
        ),
      );
      if (!mounted || current != epoch || !writeRights) return;
      final values = businessItems(result);
      setState(() {
        final combined = <String, Map<String, dynamic>>{
          if (more)
            for (final o in origins) _lotKey(o): o,
          for (final o in values) _lotKey(o): o,
        };
        origins = combined.values.toList();
        for (final o in origins) {
          originInputs.putIfAbsent(_lotKey(o), TextEditingController.new);
        }
        nextOrigins = result['next_offset'] as int?;
      });
    } catch (e) {
      if (mounted && current == epoch) failure(e);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> freshWrite() async {
    await widget.session.load();
    if (widget.session.error != null || widget.session.loading)
      throw const ApiException(
        0,
        'Die aktuellen Berechtigungen konnten noch nicht bestätigt werden.',
      );
    if (!mayRead ||
        !widget.session.canWrite('accounting.prepare') ||
        !widget.session.canWrite('finance.write'))
      throw const ApiException(
        403,
        'Globale EÜR-Vorbereitung und Finanzschreibrechte sind erforderlich.',
      );
    if (!widget.session.sectionEnabled('finance'))
      throw const ApiException(
        423,
        'Finanzen ist fachlich deaktiviert. Bestätigte Ursprungsbindungen bleiben lesbar.',
      );
    final fresh = businessMap(await widget.session.read(path));
    if (!writeRights)
      throw const ApiException(403, 'Die aktuelle Berechtigung fehlt.');
    if (fresh['writes_allowed'] != true)
      throw const ApiException(
        423,
        'Neue Ursprungsbindungen sind derzeit gesperrt.',
      );
  }

  Future<void> prepare() async {
    if (!mayWrite || selected == null || pending) return;
    final current = epoch;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      final explanation = reason.text.trim();
      if (explanation.isEmpty ||
          explanation.length > 1000 ||
          RegExp(r'[\x00-\x1f\x7f]').hasMatch(explanation))
        throw const FormatException(
          'Bitte eine einzeilige Begründung mit 1 bis 1000 Zeichen eingeben.',
        );
      final chosen = <Map<String, dynamic>>[],
          sources = <Map<String, dynamic>>[];
      var total = BigInt.zero;
      for (final origin in origins) {
        final text = originInputs[_lotKey(origin)]!.text.trim();
        if (text.isEmpty) continue;
        final decimal = businessDecimal(text);
        if (RegExp(r'^0+(?:\.0{1,2})?$').hasMatch(decimal)) continue;
        final value = accountingAmount(decimal), cents = _cents(value);
        if (cents > _cents(origin['remaining_amount']))
          throw const FormatException(
            'Ein Ursprungsbetrag überschreitet den noch rücknehmbaren Bruttobetrag.',
          );
        chosen.add({
          'entry_id': origin['entry_id'],
          'group_id': origin['group_id'],
          'lot_state_hash': origin['lot_state_hash'],
          'amount': value,
        });
        sources.add(origin);
        total += cents;
      }
      if (chosen.isEmpty ||
          chosen.length > 500 ||
          total != _cents(selected!['amount']))
        throw const FormatException(
          'Die Ursprungsbeträge müssen zusammen genau den ganzen Erstattungsanteil ergeben.',
        );
      final body = <String, dynamic>{
        'source_hash': state!['source_hash'],
        'expected_revision': state!['revision'],
        'state_hash': state!['state_hash'],
        'portion_id': selected!['portion_id'],
        'portion_state_hash': selected!['portion_state_hash'],
        'origins': chosen,
        'reason': explanation,
      };
      await freshWrite();
      if (!mounted || current != epoch || !writeRights) return;
      await authorizeOrigins(sources);
      if (!mounted || current != epoch || !writeRights) return;
      final proposal = businessMap(
        await widget.session.previewRefundOrigins(widget.eventId, body),
      );
      if (!mounted || current != epoch || !writeRights) return;
      setState(() {
        preview = proposal;
        confirmBody = {
          ...body,
          'preview_hash': proposal['preview_hash'],
          'confirmation': true,
        };
        continuing = false;
      });
    } catch (e) {
      if (mounted && current == epoch) failure(e);
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  void requireContinuation() {
    if (continuing && !pending)
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden, bevor Sie eine neue Ursprungsbindung beginnen.',
      );
  }

  Future<void> confirm() async {
    if (!mayWrite || confirmBody == null) return;
    final current = epoch, body = confirmBody!, shownPreview = preview;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      requireContinuation();
      await freshWrite();
      if (!mounted || current != epoch || !writeRights) return;
      if (shownPreview != null) {
        await authorizeOrigins(businessItems(shownPreview['lines']));
        if (!mounted || current != epoch || !writeRights) return;
      }
      requireContinuation();
      final wasContinuation = continuing;
      continuing = true;
      final response = wasContinuation
          ? widget.session.repeatRefundOriginCommand(widget.eventId)
          : widget.session.command(key, '$path/confirm', body);
      if (shownPreview != null)
        widget.session.preservePendingEditor(key, {'preview': shownPreview});
      await response;
      if (!mounted || current != epoch || !mayRead) return;
      setState(() {
        continuing = false;
        preview = confirmBody = null;
        message = 'Erstattungsursprung bestätigt. Geldfluss und offene Posten bleiben unverändert.';
      });
      await load();
    } catch (e) {
      if (mounted && current == epoch) {
        failure(e);
        if (mayRead &&
            !pending &&
            e is ApiException &&
            e.status != 0 &&
            e.status < 500 &&
            e.status != 429 &&
            e.status != 423)
          setState(() {
            preview = confirmBody = null;
            continuing = false;
          });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget heading(String text) =>
      Text(text, style: Theme.of(context).textTheme.titleMedium);
  Widget card(List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children
            .map(
              (w) =>
                  Padding(padding: const EdgeInsets.only(bottom: 8), child: w),
            )
            .toList(),
      ),
    ),
  );
  Widget portionTitle(Map<String, dynamic> portion) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading(
        '${portion['number'] ?? 'Rechnung'} · ${portion['party_name'] ?? 'Bestätigter Kunde'}',
      ),
      Text('Ganzer Erstattungsanteil: ${businessMoney(portion['amount'])}'),
    ],
  );

  Widget originIdentity(
    Map<String, dynamic> origin, {
    bool line = false,
  }) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading('Dokumentierte Aufteilung Nr. ${origin['component_sequence']}'),
      Text(
        'Ursprünglicher Zahlungstag: ${businessDate(origin[line ? 'origin_cash_date' : 'cash_date'])}',
      ),
      Text(
        'Nachweis: ${origin[line ? 'origin_evidence_reference' : 'evidence_reference']}',
      ),
      if ('${origin[line ? 'origin_reference' : 'reference'] ?? ''}'.isNotEmpty)
        Text(
          'Verwendungszweck: ${origin[line ? 'origin_reference' : 'reference']}',
        ),
      Text(
        'Beleggruppe · ${'${origin['rate']}'.replaceAll('.', ',')} % · Kategorie laut Beleg: ${origin['category']}',
      ),
      if ('${origin['tax_reason'] ?? ''}'.isNotEmpty)
        Text('${origin['tax_reason']}'),
    ],
  );
  String amounts(
    Map<String, dynamic> v,
    String net,
    String tax,
    String gross,
  ) =>
      'netto ${businessMoney(v[net])} · ausgewiesene Steuer ${businessMoney(v[tax])} · brutto ${businessMoney(v[gross])}';

  Widget confirmationActions() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      FilledButton(
        onPressed: mayWrite ? confirm : null,
        child: Text(
          continuing
              ? 'Unverändert erneut senden'
              : 'Erstattungsursprung verbindlich bestätigen',
        ),
      ),
      if (!continuing && !pending)
        TextButton(
          onPressed: busy
              ? null
              : () => setState(() {
                  preview = confirmBody = null;
                }),
          child: const Text('Ursprungsbeträge ändern'),
        ),
    ],
  );
  Widget proof(Map<String, dynamic> value, {required bool historical}) => card([
    heading(
      historical
          ? 'Bestätigte Ursprungsbindung Nr. ${value['revision']}'
          : continuing
          ? 'Unbestätigte Übertragung · ursprüngliche Vorschau'
          : 'Erstattungsursprung prüfen',
    ),
    portionTitle(businessMap(value['portion'])),
    Text('Erstattungstag: ${businessDate(value['cash_date'])}'),
    Text('Erstattungsnachweis: ${value['evidence_reference']}'),
    if ('${value['reference'] ?? ''}'.isNotEmpty)
      Text('Verwendungszweck: ${value['reference']}'),
    Text('Dokumentierte Rücknahme: ${amounts(value, 'net', 'tax', 'amount')}'),
    Text('Begründung: ${value['reason']}'),
    for (final line in businessItems(value['lines'])) ...[
      originIdentity(line, line: true),
      Text('Dieser Rücknahmeanteil: ${amounts(line, 'net', 'tax', 'amount')}'),
      Text(
        'Zuvor zurückgenommen: ${amounts(line, 'net_before', 'tax_before', 'gross_before')}',
      ),
      Text(
        'Danach zurückgenommen: ${amounts(line, 'net_after', 'tax_after', 'gross_after')}',
      ),
      Text(
        'Danach noch rücknehmbar: ${amounts(line, 'remaining_net', 'remaining_tax', 'remaining_gross')}',
      ),
    ],
    const Text(
      'Die steuerliche Einordnung bleibt offen. Diese Ursprungsbindung gibt keine Belegbeträge für neue Aufteilungen frei.',
    ),
    if (historical)
      Text('Bestätigt: ${businessDate(value['created_at'], time: true)}')
    else
      confirmationActions(),
  ]);

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Erstattungsursprünge'),
      actions: [
        IconButton(
          tooltip: 'Erstattungsursprünge aktualisieren',
          onPressed: loading || busy ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !mayRead
        ? BusinessEmpty(
            'Erstattungsursprünge nicht freigegeben',
            error ?? 'Globale Finanz- und EÜR-Leserechte sowie die Serverfreigabe sind erforderlich.',
          )
        : ListView(
            controller: scroll,
            padding: const EdgeInsets.all(24),
            children: [
              const Notice(
                'Hier wird die Herkunft einer bereits erfassten Erstattung dokumentiert. Es entstehen keine neue Zahlung, keine neue Rechnungszuordnung und kein Steuerergebnis. Nur freigegebene Quellen werden angezeigt.',
              ),
              if (error != null) Notice(error!, error: true),
              if (message != null) Notice(message!),
              if (loading || busy) const LinearProgressIndicator(),
              if (state != null) ...[
                card([
                  heading(
                    'Bestätigter Geldfluss: ${businessMoney(state!['amount'])}',
                  ),
                  Text('Erstattungstag: ${businessDate(state!['cash_date'])}'),
                  Text('Nachweis: ${state!['evidence_reference']}'),
                  if ('${state!['reference'] ?? ''}'.isNotEmpty)
                    Text('Verwendungszweck: ${state!['reference']}'),
                  Text(
                    'Ursprung dokumentiert: ${businessMoney(state!['origin_documented_amount'])} · Noch ungeklärt: ${businessMoney(state!['origin_unresolved_amount'])}',
                  ),
                  Text(
                    'Davon noch keiner Rechnung zugeordnet: ${businessMoney(state!['unallocated_amount'])}',
                  ),
                  if (state!['eligible'] != true)
                    Text(_blockedText(state!['blocked_reason'])),
                  if (!writeRights || state!['writes_allowed'] != true)
                    const Text(
                      'Bestätigte Ursprungsbindungen bleiben lesbar. Neue Bindungen sind derzeit nicht freigegeben.',
                    ),
                ]),
                if (preview != null)
                  proof(preview!, historical: false)
                else if (continuing && confirmBody != null)
                  card([
                    heading('Unbestätigte Ursprungsbindung'),
                    const Text(
                      'Die ursprüngliche Bestätigung kann unverändert erneut gesendet werden. Gespeicherte Ursprungsdetails werden hier nicht angezeigt.',
                    ),
                    confirmationActions(),
                  ])
                else if (writeRights &&
                    state!['writes_allowed'] == true &&
                    state!['eligible'] == true) ...[
                  heading('Ganzen Erstattungsanteil auswählen'),
                  if (selected == null) ...[
                    for (final portion in portions)
                      card([
                        portionTitle(portion),
                        if (portion['eligible'] == true)
                          OutlinedButton(
                            onPressed: mayWrite ? () => choose(portion) : null,
                            child: const Text(
                              'Ursprünge für diesen Anteil wählen',
                            ),
                          )
                        else
                          Text(_blockedText(portion['blocked_reason'])),
                      ]),
                    if (!loading && portions.isEmpty)
                      const BusinessEmpty(
                        'Keine offenen Erstattungsanteile',
                        'Für diesen Geldfluss sind derzeit keine weiteren Rechnungsanteile verfügbar.',
                      ),
                    if (nextPortions != null)
                      OutlinedButton(
                        onPressed: mayWrite
                            ? () => more(historyPage: false)
                            : null,
                        child: const Text('Weitere Erstattungsanteile laden'),
                      ),
                  ] else
                    card([
                      portionTitle(selected!),
                      TextButton(
                        onPressed: mayWrite
                            ? () => setState(() {
                                selected = null;
                                origins = [];
                              })
                            : null,
                        child: const Text(
                          'Anderen Erstattungsanteil auswählen',
                        ),
                      ),
                      const Text(
                        'Wählen Sie die ursprünglichen Zahlungsanteile ausdrücklich durch einen Bruttobetrag. Die Summe muss genau den ganzen Erstattungsanteil ergeben. Leere Felder oder null lassen einen Ursprung aus.',
                      ),
                      for (final origin in origins) ...[
                        const Divider(),
                        originIdentity(origin),
                        Text(
                          'Ursprünglich dokumentiert: ${amounts(origin, 'net', 'tax', 'amount')}',
                        ),
                        Text(
                          'Bereits zurückgenommen: ${amounts(origin, 'returned_net', 'returned_tax', 'returned_amount')}',
                        ),
                        Text(
                          'Noch rücknehmbar: ${amounts(origin, 'remaining_net', 'remaining_tax', 'remaining_amount')}',
                        ),
                        TextField(
                          key: ValueKey('refund-origin-${_lotKey(origin)}'),
                          controller: originInputs[_lotKey(origin)],
                          enabled: mayWrite,
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                          decoration: const InputDecoration(
                            labelText: 'Bruttoanteil aus diesem Ursprung (€)',
                          ),
                        ),
                      ],
                      if (!loading && origins.isEmpty)
                        const Text(
                          'Keine passenden freigegebenen Ursprünge verfügbar. Die Erstattung bleibt ungeklärt.',
                        ),
                      if (nextOrigins != null)
                        OutlinedButton(
                          onPressed: mayWrite
                              ? () => loadOrigins(more: true)
                              : null,
                          child: const Text('Weitere Ursprünge laden'),
                        ),
                      TextField(
                        key: const ValueKey('refund-reason'),
                        controller: reason,
                        enabled: mayWrite,
                        decoration: const InputDecoration(
                          labelText: 'Begründung der Ursprungsbindung',
                        ),
                      ),
                      OutlinedButton(
                        onPressed: mayWrite && origins.isNotEmpty
                            ? prepare
                            : null,
                        child: const Text('Erstattungsursprung vorschauen'),
                      ),
                    ]),
                ],
                const SizedBox(height: 16),
                heading('Historie der Erstattungsursprünge'),
                if (!loading && history.isEmpty)
                  const Text('Noch keine Ursprungsbindung bestätigt.'),
                for (final entry in history) proof(entry, historical: true),
                if (nextHistory != null)
                  OutlinedButton(
                    onPressed: loading || busy
                        ? null
                        : () => more(historyPage: true),
                    child: const Text('Weitere Ursprungsbindungen laden'),
                  ),
              ],
            ],
          ),
  );
}

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting.dart'
    show accountingAmount, businessAccountingReadable;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

bool businessAllocationsReadable(BusinessSession session) =>
    businessAccountingReadable(session) &&
    session.hasFeature('accounting_payment_allocation') &&
    session.hasModule('accounting_allocations');

const _blocked = {
  'unsupported_payment':
      'Diese Zahlungsart unterstützt keine zusätzliche Zuordnung.',
  'unsupported_source_documents': 'Die bestehenden Rechnungsarten unterstützen keine zusätzliche Zuordnung.',
  'missing_customer':
      'Die unveränderliche Kundenbindung einer bestehenden Rechnung fehlt.',
  'mixed_customers':
      'Die Zahlung betrifft verschiedene Kunden und benötigt eine Klärung.',
  'fully_allocated': 'Die Zahlung ist vollständig zugeordnet.',
  'overallocated': 'Die bisherigen Zuordnungen überschreiten den Zahlungsbetrag und benötigen eine Klärung.',
};

class BusinessPaymentAllocationsPage extends StatefulWidget {
  const BusinessPaymentAllocationsPage({
    super.key,
    required this.session,
    required this.paymentId,
  });
  final BusinessSession session;
  final String paymentId;
  @override
  State<BusinessPaymentAllocationsPage> createState() =>
      _BusinessPaymentAllocationsPageState();
}

class _BusinessPaymentAllocationsPageState
    extends State<BusinessPaymentAllocationsPage> {
  Map<String, dynamic>? state, selected, preview, assignBody;
  List<Map<String, dynamic>> candidates = [], history = [];
  final amount = TextEditingController(), reason = TextEditingController();
  bool customerConfirmed = false, loading = false, busy = false, denied = false;
  bool continuing = false;
  int epoch = 0;
  int? nextCandidates, nextHistory;
  String? error, message;
  String get path => '/accounting/allocations/payments/${widget.paymentId}';
  String get key => 'accounting-allocation-${widget.paymentId}';
  bool get mayRead => businessAllocationsReadable(widget.session) && !denied;
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
    amount.dispose();
    reason.dispose();
    super.dispose();
  }

  void clear() {
    epoch++;
    state = selected = preview = assignBody = null;
    candidates = [];
    history = [];
    amount.clear();
    reason.clear();
    nextCandidates = nextHistory = null;
    customerConfirmed = continuing = loading = busy = false;
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!businessAllocationsReadable(widget.session))
        clear();
      else if (!writeRights)
        candidates = [];
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
          : 'Die Zahlungszuordnung konnte nicht geladen werden.';
    });
  }

  void restorePending() {
    final body = widget.session.pendingCommandValues(key, path: '$path/assign');
    if (body == null) return;
    final saved = widget.session.pendingEditorValues(key);
    assignBody = body;
    preview = saved?['preview'] is Map
        ? businessMap(saved!['preview'])
        : {
            ...body,
            'document': {
              'document_id': body['document_id'],
              'customer_id': body['customer_id'],
            },
          };
    continuing = true;
  }

  Future<void> load() async {
    if (!businessAllocationsReadable(widget.session)) return;
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final fresh = businessMap(await widget.session.read(path));
      final pendingBody = widget.session.pendingCommandValues(
        key,
        path: '$path/assign',
      );
      if (pendingBody != null) {
        // An unreceived assignment has not yet added its target project to the
        // payment's access scope. Authorize that target before restoring RAM.
        await widget.session.read('/documents/${pendingBody['document_id']}');
      }
      final result = await Future.wait([
        widget.session.read('$path/history?limit=50&offset=0'),
        if (businessAllocationsReadable(widget.session) &&
            widget.session.canWrite('accounting.prepare') &&
            widget.session.canWrite('finance.write') &&
            widget.session.sectionEnabled('finance') &&
            fresh['writes_allowed'] == true &&
            fresh['eligible'] == true)
          widget.session.read('$path/candidates?limit=50&offset=0'),
      ]);
      if (!mounted ||
          current != epoch ||
          !businessAllocationsReadable(widget.session))
        return;
      setState(() {
        denied = false;
        state = fresh;
        final h = businessMap(result[0]);
        history = businessItems(h);
        nextHistory = h['next_offset'] as int?;
        candidates = result.length == 2 ? businessItems(result[1]) : [];
        nextCandidates = result.length == 2
            ? businessMap(result[1])['next_offset'] as int?
            : null;
        selected = preview = assignBody = null;
        customerConfirmed = continuing = false;
        amount.clear();
        reason.clear();
        restorePending();
      });
    } catch (e) {
      if (mounted && current == epoch) failure(e);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> more({required bool historyPage}) async {
    final offset = historyPage ? nextHistory : nextCandidates;
    if (offset == null ||
        loading ||
        busy ||
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
          '$path/${historyPage ? 'history' : 'candidates'}?limit=50&offset=$offset',
        ),
      );
      if (!mounted || current != epoch || !mayRead) return;
      setState(() {
        if (historyPage) {
          history = [...history, ...businessItems(result)];
          nextHistory = result['next_offset'] as int?;
        } else {
          candidates = [...candidates, ...businessItems(result)];
          nextCandidates = result['next_offset'] as int?;
        }
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
        'Finanzen ist fachlich deaktiviert. Die Historie bleibt lesbar.',
      );
    final fresh = businessMap(await widget.session.read(path));
    if (!writeRights)
      throw const ApiException(403, 'Die aktuelle Berechtigung fehlt.');
    if (fresh['writes_allowed'] != true)
      throw const ApiException(423, 'Neue Zuordnungen sind derzeit gesperrt.');
  }

  Future<void> prepare() async {
    if (!mayWrite || selected == null || pending) return;
    final current = epoch;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      if (!customerConfirmed)
        throw const FormatException(
          'Bitte den angezeigten Kunden ausdrücklich bestätigen.',
        );
      final value = accountingAmount(amount.text);
      final explanation = reason.text.trim();
      if (explanation.isEmpty ||
          explanation.length > 1000 ||
          RegExp(r'[\x00-\x1f\x7f]').hasMatch(explanation))
        throw const FormatException(
          'Bitte eine einzeilige Begründung mit 1 bis 1000 Zeichen eingeben.',
        );
      final body = <String, dynamic>{
        'source_hash': state!['source_hash'],
        'expected_revision': state!['revision'],
        'state_hash': state!['state_hash'],
        'customer_id': selected!['customer_id'],
        'document_id': selected!['document_id'],
        'document_state_hash': selected!['document_state_hash'],
        'amount': value,
        'reason': explanation,
      };
      await freshWrite();
      if (!mounted || current != epoch || !writeRights) return;
      final proposed = businessMap(
        await widget.session.previewPaymentAllocation(widget.paymentId, body),
      );
      if (!mounted || current != epoch || !writeRights) return;
      setState(() {
        preview = proposed;
        assignBody = {
          ...body,
          'preview_hash': proposed['preview_hash'],
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
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden, bevor Sie einen neuen Vorgang beginnen.',
      );
  }

  Future<void> assign() async {
    if (!mayWrite || preview == null || assignBody == null) return;
    final current = epoch;
    final body = assignBody!;
    final shownPreview = preview!;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      requireContinuation();
      await freshWrite();
      if (!mounted || current != epoch || !writeRights) return;
      requireContinuation();
      continuing = true;
      final response = widget.session.command(key, '$path/assign', body);
      // command has synchronously captured its immutable input before awaiting
      // transport. Preserve the shown proposal even if this page is closed.
      widget.session.preservePendingEditor(key, {'preview': shownPreview});
      await response;
      if (!mounted || current != epoch || !mayRead) return;
      setState(() {
        continuing = false;
        preview = assignBody = null;
        message =
            'Zuordnung bestätigt. Es wurde kein neuer Geldfluss angelegt.';
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
            e.status != 423) {
          setState(() {
            preview = assignBody = null;
            continuing = false;
          });
        }
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

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
  Widget heading(String text) =>
      Text(text, style: Theme.of(context).textTheme.titleMedium);

  Iterable<Map<String, dynamic>> get knownDocuments sync* {
    yield* candidates;
    for (final entry in history) {
      yield businessMap(entry['document']);
    }
  }

  String get customerBinding {
    final customer = knownDocuments
        .where((document) => document['customer_id'] == state?['customer_id'])
        .map((document) => document['buyer_name'])
        .whereType<String>()
        .where((name) => name.isNotEmpty)
        .firstOrNull;
    return customer == null
        ? 'Diese Zahlung ist an einen Kunden gebunden.'
        : 'Gebundener Kunde: $customer';
  }

  String invoiceName(Object? id) =>
      knownDocuments
          .where((document) => document['document_id'] == id)
          .map((document) => document['number'])
          .whereType<String>()
          .where((number) => number.isNotEmpty)
          .firstOrNull ??
      'Zugeordnete Rechnung';

  Widget document(Map<String, dynamic> value) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading('${value['number'] ?? 'Bestätigte Rechnung'}'),
      Text('Kunde: ${value['buyer_name'] ?? 'Bestätigter Kunde'}'),
      if (value['open'] != null)
        Text(
          'Rechnung brutto ${businessMoney(value['gross'])} · Offen ${businessMoney(value['open'])}',
        ),
    ],
  );
  Widget proof(Map<String, dynamic> value, {required bool historical}) {
    final target = businessMap(value['document']);
    return card([
      heading(
        historical
            ? 'Bestätigte Zuordnung Nr. ${value['revision']}'
            : continuing
            ? 'Unbestätigte Übertragung · ursprüngliche Vorschau'
            : 'Vorschau prüfen',
      ),
      document(target),
      Text('Zuordnungsbetrag: ${businessMoney(value['amount'])}'),
      Text('Begründung: ${value['reason']}'),
      if (value['unallocated_before'] != null)
        Text(
          'Freier Zahlungsbetrag: ${businessMoney(value['unallocated_before'])} → ${businessMoney(value['unallocated_after'])}',
        ),
      if (value['open_before'] != null)
        Text(
          'Offener Rechnungsbetrag: ${businessMoney(value['open_before'])} → ${businessMoney(value['open_after'])}',
        ),
      if (historical) ...[
        Text('Bestätigt: ${businessDate(value['created_at'], time: true)}'),
      ],
      if (!historical) ...[
        const Text(
          'Diese Zuordnung verändert die offenen Posten. Der ursprüngliche Zahlungsnachweis bleibt unverändert.',
        ),
        FilledButton(
          onPressed: mayWrite ? assign : null,
          child: Text(
            continuing
                ? 'Unverändert erneut senden'
                : 'Zuordnung verbindlich bestätigen',
          ),
        ),
        if (!continuing && !pending)
          TextButton(
            onPressed: busy
                ? null
                : () => setState(() {
                    preview = assignBody = null;
                    customerConfirmed = false;
                  }),
            child: const Text('Eingaben ändern'),
          ),
      ],
    ]);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Rechnungszuordnungen'),
      actions: [
        IconButton(
          tooltip: 'Zuordnungen aktualisieren',
          onPressed: loading || busy ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !mayRead
        ? BusinessEmpty(
            'Zahlungszuordnung nicht freigegeben',
            error ?? 'Globale Finanz- und EÜR-Leserechte sowie die Serverfreigabe sind erforderlich.',
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Notice(
                'Nur freigegebene Quellen. Zusätzliche Rechnungszuordnungen ergänzen die Zahlung. Der ursprüngliche Zahlungsnachweis bleibt unverändert. Keine steuerliche Einordnung und kein neuer Geldfluss.',
              ),
              if (error != null) Notice(error!, error: true),
              if (message != null) Notice(message!),
              if (loading || busy) const LinearProgressIndicator(),
              if (state != null) ...[
                card([
                  heading('Aktueller Zuordnungsstand'),
                  Text(
                    'Ursprünglicher Zahlungseingang: ${businessMoney(state!['amount'])}',
                  ),
                  Text(
                    'Zugeordnet: ${businessMoney(state!['allocated_amount'])} · Frei: ${businessMoney(state!['unallocated_amount'])}',
                  ),
                  if (state!['customer_id'] != null)
                    Text(customerBinding)
                  else
                    const Text(
                      'Noch keine Kundenbindung. Die erste Zuordnung bestätigt den Kunden der Zielrechnung.',
                    ),
                  for (final allocation in businessItems(state!['allocations']))
                    SelectableText(
                      '${invoiceName(allocation['document_id'])} · ${businessMoney(allocation['amount'])}',
                    ),
                  if (state!['eligible'] != true)
                    Text(
                      _blocked[state!['blocked_reason']] ??
                          'Weitere Zuordnungen benötigen eine Klärung.',
                    ),
                  if (!writeRights || state!['writes_allowed'] != true)
                    const Text(
                      'Der Stand bleibt lesbar. Neue Zuordnungen sind derzeit nicht freigegeben.',
                    ),
                ]),
                if (preview != null)
                  proof(preview!, historical: false)
                else if (writeRights &&
                    state!['writes_allowed'] == true &&
                    state!['eligible'] == true) ...[
                  heading('Rechnung auswählen'),
                  if (selected == null) ...[
                    for (final candidate in candidates)
                      card([
                        document(candidate),
                        OutlinedButton(
                          onPressed: mayWrite
                              ? () => setState(() {
                                  selected = candidate;
                                  customerConfirmed = false;
                                  amount.clear();
                                  reason.clear();
                                })
                              : null,
                          child: const Text('Diese Rechnung auswählen'),
                        ),
                      ]),
                    if (!loading && candidates.isEmpty)
                      const BusinessEmpty(
                        'Keine passende Rechnung',
                        'Für diesen Vorgang liegen keine freigegebenen normalen EUR-Rechnungen mit offenem Betrag vor.',
                      ),
                    if (nextCandidates != null)
                      OutlinedButton(
                        onPressed: mayWrite
                            ? () => more(historyPage: false)
                            : null,
                        child: const Text('Weitere Rechnungen laden'),
                      ),
                  ] else
                    card([
                      document(selected!),
                      TextButton(
                        onPressed: mayWrite
                            ? () => setState(() {
                                selected = null;
                                customerConfirmed = false;
                              })
                            : null,
                        child: const Text('Andere Rechnung auswählen'),
                      ),
                      CheckboxListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(
                          'Ich bestätige den Kunden ${selected!['buyer_name']} für diese Zahlung.',
                        ),
                        value: customerConfirmed,
                        onChanged: mayWrite
                            ? (v) =>
                                  setState(() => customerConfirmed = v == true)
                            : null,
                      ),
                      TextField(
                        key: const ValueKey('allocation-amount'),
                        controller: amount,
                        enabled: mayWrite,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Zuordnungsbetrag (€)',
                        ),
                      ),
                      TextField(
                        key: const ValueKey('allocation-reason'),
                        controller: reason,
                        enabled: mayWrite,
                        decoration: const InputDecoration(
                          labelText: 'Begründung der Zuordnung',
                        ),
                      ),
                      OutlinedButton(
                        onPressed: mayWrite ? prepare : null,
                        child: const Text('Vorschau berechnen'),
                      ),
                    ]),
                ],
                const SizedBox(height: 16),
                heading('Historie zusätzlicher Zuordnungen'),
                if (!loading && history.isEmpty)
                  const Text('Noch keine zusätzlichen Zuordnungen bestätigt.'),
                for (final entry in history) proof(entry, historical: true),
                if (nextHistory != null)
                  OutlinedButton(
                    onPressed: loading || busy
                        ? null
                        : () => more(historyPage: true),
                    child: const Text('Weitere Zuordnungen laden'),
                  ),
              ],
            ],
          ),
  );
}

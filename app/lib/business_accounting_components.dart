import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting.dart'
    show accountingAmount, businessAccountingReadable;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

bool businessComponentsReadable(BusinessSession session) =>
    businessAccountingReadable(session) &&
    session.hasFeature('accounting_document_components') &&
    session.hasModule('accounting_components');

const _blocked = {
  'refund_origin_unresolved': 'Der Ursprung dieser Erstattung ist noch ungeklärt. Eine Belegaufteilung ist derzeit nicht möglich.',
  'source_customer_unresolved':
      'Die Kundenangaben der zugeordneten Belege sind noch ungeklärt.',
  'review_changed': 'Die Belegprüfung wurde geändert. Neue Aufteilungen benötigen eine Klärung; bestätigte Aufteilungen bleiben unverändert.',
  'unsupported_document': 'Dieser Beleg benötigt eine gesonderte Prüfung.',
  'group_capacity_exceeded':
      'Der ganze Beleganteil überschreitet den noch verfügbaren Gruppenbetrag.',
  'unallocated':
      'Der verbleibende Geldbetrag ist noch keinem Beleg zugeordnet.',
  'fully_documented': 'Dieser Geldfluss ist vollständig dokumentiert.',
};
BigInt _cents(Object? value) => BigInt.parse('$value'.replaceAll('.', ''));
String _blockedText(Object? reason) =>
    _blocked[reason] ??
    'Dieser Anteil benötigt eine Klärung und kann derzeit nicht neu aufgeteilt werden.';
String _groupLabel(Map<String, dynamic> group) => group['rate'] == null
    ? 'Summen laut Belegprüfung'
    : 'Beleggruppe · ${'${group['rate']}'.replaceAll('.', ',')} %';

class BusinessDocumentComponentsPage extends StatefulWidget {
  const BusinessDocumentComponentsPage({
    super.key,
    required this.session,
    required this.eventId,
  });
  final BusinessSession session;
  final String eventId;
  @override
  State<BusinessDocumentComponentsPage> createState() =>
      _BusinessDocumentComponentsPageState();
}

class _BusinessDocumentComponentsPageState
    extends State<BusinessDocumentComponentsPage> {
  Map<String, dynamic>? state, selected, preview, confirmBody;
  List<Map<String, dynamic>> portions = [], history = [];
  final groupInputs = <String, TextEditingController>{};
  final reason = TextEditingController();
  bool loading = false, busy = false, denied = false, continuing = false;
  int epoch = 0;
  int? nextPortions, nextHistory;
  String? error, message;
  String get path => '/accounting/components/events/${widget.eventId}';
  String get key => 'accounting-components-${widget.eventId}';
  bool get mayRead => businessComponentsReadable(widget.session) && !denied;
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
    for (final input in groupInputs.values) {
      input.dispose();
    }
    reason.dispose();
    super.dispose();
  }

  void clear() {
    epoch++;
    state = selected = preview = confirmBody = null;
    portions = [];
    history = [];
    nextPortions = nextHistory = null;
    for (final input in groupInputs.values) {
      input.clear();
    }
    reason.clear();
    continuing = loading = busy = false;
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!businessComponentsReadable(widget.session))
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
          : 'Die Belegaufteilung konnte nicht geladen werden.';
    });
  }

  Future<Map<String, dynamic>?> authorizedPendingPreview() async {
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
    final portion = businessMap(proposal['portion']);
    final documentId = portion['document_id'],
        receiptId = portion['receipt_id'];
    if (documentId is String &&
        RegExp(r'^[a-f0-9]{32}$').hasMatch(documentId)) {
      await widget.session.read('/documents/$documentId');
    } else if (receiptId is String &&
        RegExp(r'^[a-f0-9]{32}$').hasMatch(receiptId)) {
      await widget.session.read('/finance/receipts/$receiptId');
    } else {
      return null;
    }
    return proposal;
  }

  Future<void> load() async {
    if (!businessComponentsReadable(widget.session)) return;
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
        if (businessComponentsReadable(widget.session) &&
            widget.session.canWrite('accounting.prepare') &&
            widget.session.canWrite('finance.write') &&
            widget.session.sectionEnabled('finance') &&
            fresh['writes_allowed'] == true &&
            fresh['eligible'] == true)
          widget.session.read('$path/portions?limit=50&offset=0'),
      ]);
      if (!mounted ||
          current != epoch ||
          !businessComponentsReadable(widget.session))
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
        preview = saved;
        confirmBody = currentPending;
        continuing = confirmBody != null;
        for (final input in groupInputs.values) {
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

  void choose(Map<String, dynamic> portion) {
    for (final input in groupInputs.values) {
      input.clear();
    }
    final groups = businessItems(portion['groups']);
    for (final group in groups) {
      groupInputs.putIfAbsent(
        '${group['group_id']}',
        TextEditingController.new,
      );
    }
    if (groups.length == 1)
      groupInputs['${groups.single['group_id']}']!.text = '${portion['amount']}'
          .replaceAll('.', ',');
    setState(() {
      selected = portion;
      reason.clear();
      error = null;
    });
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
        'Finanzen ist fachlich deaktiviert. Bestätigte Aufteilungen bleiben lesbar.',
      );
    final fresh = businessMap(await widget.session.read(path));
    if (!writeRights)
      throw const ApiException(403, 'Die aktuelle Berechtigung fehlt.');
    if (fresh['writes_allowed'] != true)
      throw const ApiException(423, 'Neue Aufteilungen sind derzeit gesperrt.');
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
      final groups = <Map<String, dynamic>>[];
      var total = BigInt.zero;
      for (final group in businessItems(selected!['groups'])) {
        final text = groupInputs['${group['group_id']}']!.text.trim();
        if (text.isEmpty) continue;
        final decimal = businessDecimal(text);
        if (RegExp(r'^0+(?:\.0{1,2})?$').hasMatch(decimal)) continue;
        final value = accountingAmount(decimal);
        final cents = _cents(value);
        if (cents > _cents(group['remaining_gross']))
          throw const FormatException(
            'Ein Gruppenbetrag überschreitet den noch verfügbaren Bruttobetrag.',
          );
        groups.add({'group_id': group['group_id'], 'amount': value});
        total += cents;
      }
      if (groups.isEmpty || total != _cents(selected!['amount']))
        throw const FormatException(
          'Die Gruppenbeträge müssen zusammen genau den ganzen Beleganteil ergeben.',
        );
      final body = <String, dynamic>{
        'source_hash': state!['source_hash'],
        'expected_revision': state!['revision'],
        'state_hash': state!['state_hash'],
        'portion_id': selected!['portion_id'],
        'portion_state_hash': selected!['portion_state_hash'],
        'groups': groups,
        'reason': explanation,
      };
      await freshWrite();
      if (!mounted || current != epoch || !writeRights) return;
      final proposal = businessMap(
        await widget.session.previewDocumentComponents(widget.eventId, body),
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
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte den Stand neu laden, bevor Sie eine neue Aufteilung beginnen.',
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
      requireContinuation();
      final wasContinuation = continuing;
      continuing = true;
      final response = wasContinuation
          ? widget.session.repeatDocumentComponentCommand(widget.eventId)
          : widget.session.command(key, '$path/confirm', body);
      if (shownPreview != null)
        widget.session.preservePendingEditor(key, {'preview': shownPreview});
      await response;
      if (!mounted || current != epoch || !mayRead) return;
      setState(() {
        continuing = false;
        preview = confirmBody = null;
        message = 'Belegaufteilung bestätigt. Geldfluss und offene Posten bleiben unverändert.';
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
        '${portion['number'] ?? 'Geprüfter Beleg'} · ${portion['party_name'] ?? 'Bestätigter Geschäftspartner'}',
      ),
      Text('Ganzer Beleganteil: ${businessMoney(portion['amount'])}'),
      if (portion['review_revision'] != null)
        Text('Bestätigte Belegprüfung Nr. ${portion['review_revision']}'),
    ],
  );
  Widget groupCapacity(Map<String, dynamic> group) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading(_groupLabel(group)),
      if (group['category'] != null)
        Text('Kategorie laut Beleg: ${group['category']}'),
      if (group['reason'] != null && '${group['reason']}'.isNotEmpty)
        Text('${group['reason']}'),
      Text(
        'Laut Beleg: netto ${businessMoney(group['net'])} · ausgewiesene Steuer ${businessMoney(group['tax'])} · brutto ${businessMoney(group['gross'])}',
      ),
      Text(
        'Bereits dokumentiert: netto ${businessMoney(group['documented_net'])} · ausgewiesene Steuer ${businessMoney(group['documented_tax'])} · brutto ${businessMoney(group['documented_gross'])}',
      ),
      Text(
        'Noch verfügbar: netto ${businessMoney(group['remaining_net'])} · ausgewiesene Steuer ${businessMoney(group['remaining_tax'])} · brutto ${businessMoney(group['remaining_gross'])}',
      ),
    ],
  );

  Widget groupIdentity(Map<String, dynamic> group) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading(_groupLabel(group)),
      if (group['category'] != null)
        Text('Kategorie laut Beleg: ${group['category']}'),
      if (group['reason'] != null && '${group['reason']}'.isNotEmpty)
        Text('${group['reason']}'),
    ],
  );
  Widget confirmationActions() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      FilledButton(
        onPressed: mayWrite ? confirm : null,
        child: Text(
          continuing
              ? 'Unverändert erneut senden'
              : 'Belegaufteilung verbindlich bestätigen',
        ),
      ),
      if (!continuing && !pending)
        TextButton(
          onPressed: busy
              ? null
              : () => setState(() {
                  preview = confirmBody = null;
                }),
          child: const Text('Gruppenbeträge ändern'),
        ),
    ],
  );
  Widget proof(Map<String, dynamic> value, {required bool historical}) {
    final portion = businessMap(value['portion']);
    final groups = businessItems(portion['groups']);
    final supplier = portion['kind'] == 'supplier_payout';
    return card([
      heading(
        historical
            ? 'Bestätigte Aufteilung Nr. ${value['revision']}'
            : continuing
            ? 'Unbestätigte Übertragung · ursprüngliche Vorschau'
            : 'Belegaufteilung prüfen',
      ),
      portionTitle(portion),
      Text('Belegter Nettoanteil: ${businessMoney(value['net'])}'),
      Text(
        '${supplier ? 'Ausgewiesener Steueranteil laut Prüfung' : 'Ausgewiesener Steueranteil laut Beleg'}: ${businessMoney(value['tax'])}',
      ),
      Text('Bruttoanteil: ${businessMoney(value['amount'])}'),
      Text('Begründung: ${value['reason']}'),
      for (final line in businessItems(value['lines'])) ...[
        groupIdentity(
          groups.firstWhere((g) => g['group_id'] == line['group_id']),
        ),
        Text(
          'Dieser Anteil: netto ${businessMoney(line['net'])} · ausgewiesene Steuer ${businessMoney(line['tax'])} · brutto ${businessMoney(line['amount'])}',
        ),
        Text(
          'Dokumentierter Gruppenbetrag: ${businessMoney(line['gross_before'])} → ${businessMoney(line['gross_after'])}',
        ),
        Text(
          'Danach noch verfügbar: ${businessMoney(line['remaining_gross'])} brutto',
        ),
      ],
      const Text('Die steuerliche Einordnung ist weiterhin offen.'),
      if (historical)
        Text('Bestätigt: ${businessDate(value['created_at'], time: true)}')
      else
        confirmationActions(),
    ]);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Dokumentarische Belegaufteilung'),
      actions: [
        IconButton(
          tooltip: 'Belegaufteilungen aktualisieren',
          onPressed: loading || busy ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !mayRead
        ? BusinessEmpty(
            'Belegaufteilung nicht freigegeben',
            error ?? 'Globale Finanz- und EÜR-Leserechte sowie die Serverfreigabe sind erforderlich.',
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Notice(
                'Hier werden ausgewiesene Belegbeträge dokumentiert. Die steuerliche Einordnung bleibt offen. Es entstehen keine neue Zahlung und keine neue Rechnungszuordnung.',
              ),
              if (error != null) Notice(error!, error: true),
              if (message != null) Notice(message!),
              if (loading || busy) const LinearProgressIndicator(),
              if (state != null) ...[
                card([
                  heading(
                    'Bestätigter Geldfluss: ${businessMoney(state!['amount'])}',
                  ),
                  Text(
                    'Dokumentiert: ${businessMoney(state!['documented_amount'])} · Noch nicht dokumentiert: ${businessMoney(state!['undocumented_amount'])}',
                  ),
                  Text(
                    'Davon noch keinem Beleg zugeordnet: ${businessMoney(state!['unallocated_amount'])}',
                  ),
                  if (state!['eligible'] != true)
                    Text(_blockedText(state!['blocked_reason'])),
                  if (!writeRights || state!['writes_allowed'] != true)
                    const Text(
                      'Bestätigte Aufteilungen bleiben lesbar. Neue Aufteilungen sind derzeit nicht freigegeben.',
                    ),
                ]),
                if (preview != null)
                  proof(preview!, historical: false)
                else if (continuing && confirmBody != null)
                  card([
                    heading('Unbestätigte Belegaufteilung'),
                    const Text(
                      'Die ursprüngliche Bestätigung kann unverändert erneut gesendet werden. Gespeicherte Belegdetails werden hier nicht angezeigt.',
                    ),
                    confirmationActions(),
                  ])
                else if (writeRights &&
                    state!['writes_allowed'] == true &&
                    state!['eligible'] == true) ...[
                  heading('Ganzen Beleganteil auswählen'),
                  if (selected == null) ...[
                    for (final portion in portions)
                      card([
                        portionTitle(portion),
                        if (portion['eligible'] == true)
                          OutlinedButton(
                            onPressed: mayWrite ? () => choose(portion) : null,
                            child: const Text('Diesen Beleganteil aufteilen'),
                          )
                        else
                          Text(_blockedText(portion['blocked_reason'])),
                      ]),
                    if (!loading && portions.isEmpty)
                      const BusinessEmpty(
                        'Keine offenen Beleganteile',
                        'Für diesen Geldfluss sind derzeit keine weiteren Beleganteile verfügbar.',
                      ),
                    if (nextPortions != null)
                      OutlinedButton(
                        onPressed: mayWrite
                            ? () => more(historyPage: false)
                            : null,
                        child: const Text('Weitere Beleganteile laden'),
                      ),
                  ] else
                    card([
                      portionTitle(selected!),
                      TextButton(
                        onPressed: mayWrite
                            ? () => setState(() => selected = null)
                            : null,
                        child: const Text('Anderen Beleganteil auswählen'),
                      ),
                      const Text(
                        'Die Bruttobeträge müssen zusammen genau den ganzen Beleganteil ergeben. Leere Felder oder null lassen eine Gruppe aus.',
                      ),
                      for (final group in businessItems(
                        selected!['groups'],
                      )) ...[
                        groupCapacity(group),
                        TextField(
                          key: ValueKey('component-group-${group['group_id']}'),
                          controller: groupInputs['${group['group_id']}'],
                          enabled: mayWrite,
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                          decoration: const InputDecoration(
                            labelText:
                                'Bestätigter Bruttoanteil dieser Gruppe (€)',
                          ),
                        ),
                      ],
                      TextField(
                        key: const ValueKey('component-reason'),
                        controller: reason,
                        enabled: mayWrite,
                        decoration: const InputDecoration(
                          labelText: 'Begründung der Belegaufteilung',
                        ),
                      ),
                      OutlinedButton(
                        onPressed: mayWrite ? prepare : null,
                        child: const Text('Belegaufteilung vorschauen'),
                      ),
                    ]),
                ],
                const SizedBox(height: 16),
                heading('Historie der Belegaufteilungen'),
                if (!loading && history.isEmpty)
                  const Text('Noch keine Belegaufteilung bestätigt.'),
                for (final entry in history) proof(entry, historical: true),
                if (nextHistory != null)
                  OutlinedButton(
                    onPressed: loading || busy
                        ? null
                        : () => more(historyPage: true),
                    child: const Text('Weitere Aufteilungen laden'),
                  ),
              ],
            ],
          ),
  );
}

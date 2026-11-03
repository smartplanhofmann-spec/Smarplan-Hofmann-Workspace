import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting.dart'
    show accountingAmount, businessAccountingReadable;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

bool businessCapacityReadable(BusinessSession session) =>
    businessAccountingReadable(session) &&
    session.hasFeature('accounting_document_component_reuse') &&
    session.hasModule('accounting_capacity');

BigInt _cents(Object? value) => BigInt.parse('$value'.replaceAll('.', ''));
String _blocked(Object? reason) =>
    const {
      'refund_origin_unresolved': 'Mindestens eine zugeordnete Erstattung benötigt noch eine bestätigte Herkunft. Zusätzliche zurückgenommene Beträge bleiben gesperrt.',
      'source_access_required':
          'Die erforderlichen Quellen sind nicht vollständig freigegeben.',
      'receipt_before_capacity': 'Der Zahlungstag liegt vor dem frühesten zulässigen Tag der verfügbaren Belegbeträge.',
      'group_capacity_exceeded':
          'Der ganze Beleganteil überschreitet die verfügbaren Gruppenbeträge.',
      'source_customer_unresolved':
          'Die Kundenbindung der ursprünglichen Belege ist noch ungeklärt.',
      'unsupported_document': 'Dieser Beleg benötigt eine gesonderte Prüfung.',
      'unallocated':
          'Der verbleibende Geldbetrag ist noch keiner Rechnung zugeordnet.',
      'fully_documented': 'Dieser Geldfluss ist vollständig dokumentiert.',
      'not_customer_receipt': 'Für diesen Geldfluss ist keine Wiederverwendung zurückgenommener Rechnungsbeträge vorgesehen.',
      'legacy_writer_required': 'Diese Rechnung benötigt die bisherige Belegaufteilung. Bitte den Stand neu laden.',
    }[reason] ??
    'Dieser Anteil benötigt eine Klärung.';

class BusinessReusableComponentsPage extends StatefulWidget {
  const BusinessReusableComponentsPage({
    super.key,
    required this.session,
    required this.eventId,
  });
  final BusinessSession session;
  final String eventId;
  @override
  State<BusinessReusableComponentsPage> createState() =>
      _BusinessReusableComponentsPageState();
}

class _BusinessReusableComponentsPageState
    extends State<BusinessReusableComponentsPage> {
  Map<String, dynamic>? state,
      selected,
      writerState,
      writerPortion,
      preview,
      confirmBody;
  List<Map<String, dynamic>> portions = [], history = [], legacyHistory = [];
  final inputs = <String, TextEditingController>{};
  final reason = TextEditingController();
  final scroll = ScrollController();
  int epoch = 0;
  int? nextPortions, nextHistory, nextLegacyHistory;
  bool loading = false, busy = false, denied = false, capacityAccepted = false;
  String? error, message, confirmPath;
  String get path => '/accounting/components/v2/events/${widget.eventId}';
  String get legacyPath => '/accounting/components/events/${widget.eventId}';
  String get key => 'accounting-components-${widget.eventId}';
  bool get pending => widget.session.pending(key);
  bool get mayRead => businessCapacityReadable(widget.session) && !denied;
  bool get writeRights =>
      mayRead &&
      widget.session.canWrite('accounting.prepare') &&
      widget.session.canWrite('finance.write') &&
      widget.session.sectionEnabled('finance');
  bool get mayWrite =>
      writeRights &&
      state?['writes_allowed'] == true &&
      widget.session.error == null &&
      !busy &&
      !loading;
  bool get legacy => selected?['action'] == 'document_legacy';

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
    reason.dispose();
    scroll.dispose();
    for (final input in inputs.values) {
      input.dispose();
    }
    super.dispose();
  }

  void clear() {
    epoch++;
    state = selected = writerState = writerPortion = preview = confirmBody =
        null;
    portions = [];
    history = [];
    legacyHistory = [];
    nextPortions = nextHistory = nextLegacyHistory = null;
    confirmPath = null;
    loading = busy = capacityAccepted = false;
    reason.clear();
    for (final input in inputs.values) {
      input.clear();
    }
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!businessCapacityReadable(widget.session)) {
        clear();
      } else if (!writeRights) {
        selected = writerPortion = writerState = preview = confirmBody = null;
        portions = [];
        capacityAccepted = false;
      }
    });
  }

  void failure(Object exception) {
    if (!mounted) return;
    setState(() {
      if (exception is ApiException &&
          [401, 403, 404].contains(exception.status)) {
        clear();
        denied = true;
      }
      error = exception is ApiException
          ? exception.message
          : exception is FormatException
          ? exception.message
          : 'Die Belegaufteilung konnte nicht geladen werden.';
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) scroll.jumpTo(0);
    });
  }

  String? pendingFingerprint() {
    final originalPath = widget.session.pendingDocumentComponentPath(
      widget.eventId,
    );
    return originalPath == null
        ? null
        : jsonEncode({
            'path': originalPath,
            'values': widget.session.pendingCommandValues(
              key,
              path: originalPath,
            ),
          });
  }

  Future<void> load() async {
    if (!businessCapacityReadable(widget.session)) return;
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final opening = pendingFingerprint();
      final fresh = businessMap(await widget.session.read(path));
      final originalPath = widget.session.pendingDocumentComponentPath(
        widget.eventId,
      );
      if (originalPath != null && originalPath != '$path/confirm') {
        // Stored details remain hidden even after this fresh whole-source check.
        await widget.session.read(
          originalPath.replaceFirst(RegExp(r'/confirm$'), ''),
        );
      }
      final result = await Future.wait([
        widget.session.read('$path/history?limit=50&offset=0'),
        widget.session.read('$legacyPath/history?limit=50&offset=0'),
        if (!pending &&
            businessCapacityReadable(widget.session) &&
            widget.session.canWrite('accounting.prepare') &&
            widget.session.canWrite('finance.write') &&
            widget.session.sectionEnabled('finance') &&
            fresh['writes_allowed'] == true &&
            fresh['source_kind'] == 'customer_receipt')
          widget.session.read('$path/portions?limit=50&offset=0'),
      ]);
      if (!mounted ||
          current != epoch ||
          !businessCapacityReadable(widget.session))
        return;
      if (opening != pendingFingerprint()) {
        await load();
        return;
      }
      setState(() {
        denied = false;
        state = fresh;
        history = businessItems(result[0]);
        nextHistory = businessMap(result[0])['next_offset'] as int?;
        legacyHistory = businessItems(result[1]);
        nextLegacyHistory = businessMap(result[1])['next_offset'] as int?;
        portions = result.length == 3 ? businessItems(result[2]) : [];
        nextPortions = result.length == 3
            ? businessMap(result[2])['next_offset'] as int?
            : null;
        selected = writerPortion = writerState = preview = confirmBody = null;
        confirmPath = null;
        capacityAccepted = false;
        reason.clear();
        for (final input in inputs.values) {
          input.clear();
        }
      });
    } catch (exception) {
      if (mounted && current == epoch) failure(exception);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> more(String collection) async {
    final offset = collection == 'portions'
        ? nextPortions
        : collection == 'legacy'
        ? nextLegacyHistory
        : nextHistory;
    if (offset == null ||
        !mayRead ||
        busy ||
        loading ||
        (collection == 'portions' && (!mayWrite || pending)))
      return;
    final current = ++epoch;
    setState(() => loading = true);
    try {
      final result = businessMap(
        await widget.session.read(
          '${collection == 'legacy' ? legacyPath : path}/${collection == 'portions' ? 'portions' : 'history'}?limit=50&offset=$offset',
        ),
      );
      if (!mounted || current != epoch || !mayRead) return;
      setState(() {
        final values = businessItems(result),
            next = result['next_offset'] as int?;
        if (collection == 'portions') {
          portions = [...portions, ...values];
          nextPortions = next;
        } else if (collection == 'legacy') {
          legacyHistory = [...legacyHistory, ...values];
          nextLegacyHistory = next;
        } else {
          history = [...history, ...values];
          nextHistory = next;
        }
      });
    } catch (exception) {
      if (mounted && current == epoch) failure(exception);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<Map<String, dynamic>> findLegacyPortion(String portionId) async {
    int? offset = 0;
    final visited = <int>{};
    while (offset != null && visited.add(offset)) {
      final page = businessMap(
        await widget.session.read(
          '$legacyPath/portions?limit=100&offset=$offset',
        ),
      );
      for (final portion in businessItems(page)) {
        if (portion['portion_id'] == portionId) return portion;
      }
      offset = page['next_offset'] as int?;
    }
    throw const ApiException(
      409,
      'Dieser Beleganteil ist nicht mehr verfügbar. Bitte den Stand neu laden.',
    );
  }

  Future<void> choose(Map<String, dynamic> portion) async {
    if (!mayWrite ||
        pending ||
        portion['eligible'] != true ||
        portion['action'] == null)
      return;
    final current = epoch;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      final old = portion['action'] == 'document_legacy';
      final source = old
          ? businessMap(await widget.session.read(legacyPath))
          : state!;
      final target = old
          ? await findLegacyPortion('${portion['portion_id']}')
          : portion;
      if (target['eligible'] != true || target['amount'] != portion['amount']) {
        throw const ApiException(
          409,
          'Die Belegaufteilung hat sich geändert. Bitte den Stand neu laden.',
        );
      }
      if (!mounted || current != epoch || !writeRights || pending) return;
      setState(() {
        selected = portion;
        writerState = source;
        writerPortion = target;
        preview = confirmBody = null;
        confirmPath = null;
        capacityAccepted = false;
        reason.clear();
        for (final input in inputs.values) {
          input.clear();
        }
        for (final group in businessItems(target['groups'])) {
          inputs.putIfAbsent('${group['group_id']}', TextEditingController.new);
        }
      });
    } catch (exception) {
      if (mounted && current == epoch) failure(exception);
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  bool dateAllowed(Map<String, dynamic> capacity) =>
      capacity['not_before_date'] == null ||
      '${state?['cash_date']}'.compareTo('${capacity['not_before_date']}') >= 0;

  Future<void> freshWrite() async {
    await widget.session.load();
    if (widget.session.error != null || widget.session.loading) {
      throw const ApiException(
        0,
        'Die aktuellen Berechtigungen konnten noch nicht bestätigt werden.',
      );
    }
    if (!writeRights)
      throw const ApiException(
        403,
        'Die aktuelle Berechtigung zur Belegaufteilung fehlt.',
      );
    final fresh = businessMap(await widget.session.read(path));
    if (!writeRights)
      throw const ApiException(403, 'Die aktuelle Berechtigung fehlt.');
    if (fresh['writes_allowed'] != true)
      throw const ApiException(423, 'Neue Aufteilungen sind derzeit gesperrt.');
  }

  Future<void> prepare() async {
    if (!mayWrite || selected == null || writerPortion == null || pending)
      return;
    final current = epoch;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      final explanation = reason.text.trim();
      if (explanation.isEmpty ||
          explanation.length > 1000 ||
          RegExp(r'[\x00-\x1f\x7f]').hasMatch(explanation)) {
        throw const FormatException(
          'Bitte eine einzeilige Begründung mit 1 bis 1000 Zeichen eingeben.',
        );
      }
      final groups = <Map<String, dynamic>>[];
      var total = BigInt.zero;
      for (final group in businessItems(writerPortion!['groups'])) {
        final text = inputs['${group['group_id']}']!.text.trim();
        if (text.isEmpty) continue;
        final decimal = businessDecimal(text);
        if (RegExp(r'^0+(?:\.0{1,2})?$').hasMatch(decimal)) continue;
        final amount = accountingAmount(decimal), cents = _cents(amount);
        final capacity = legacy
            ? {'gross': group['remaining_gross']}
            : businessMap(group['offered_capacity']);
        if (cents > _cents(capacity['gross']) || !dateAllowed(capacity)) {
          throw const FormatException(
            'Ein Gruppenbetrag ist für diesen Zahlungstag nicht in dieser Höhe verfügbar.',
          );
        }
        groups.add({'group_id': group['group_id'], 'amount': amount});
        total += cents;
      }
      if (groups.isEmpty ||
          groups.length > 500 ||
          total != _cents(writerPortion!['amount'])) {
        throw const FormatException(
          'Die Gruppenbeträge müssen zusammen genau den ganzen Beleganteil ergeben.',
        );
      }
      final old = legacy;
      final body = <String, dynamic>{
        'source_hash': writerState!['source_hash'],
        'expected_revision': writerState!['revision'],
        'state_hash': writerState!['state_hash'],
        'portion_id': writerPortion!['portion_id'],
        'portion_state_hash': writerPortion!['portion_state_hash'],
        if (!old) 'action': selected!['action'],
        'groups': groups,
        'reason': explanation,
      };
      await freshWrite();
      if (!mounted || current != epoch || !writeRights || pending) return;
      final proposal = businessMap(
        await (old
            ? widget.session.previewDocumentComponents(widget.eventId, body)
            : widget.session.previewReusableDocumentComponents(
                widget.eventId,
                body,
              )),
      );
      if (!mounted || current != epoch || !writeRights || pending) return;
      setState(() {
        preview = proposal;
        confirmPath = '${old ? legacyPath : path}/confirm';
        confirmBody = {
          ...body,
          'preview_hash': proposal['preview_hash'],
          'confirmation': true,
        };
        capacityAccepted = false;
      });
    } catch (exception) {
      if (mounted && current == epoch) failure(exception);
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  bool get hasChanges =>
      preview != null &&
      businessItems(preview!['capacity_changes'] ?? []).isNotEmpty;

  Future<void> confirm({bool retry = false}) async {
    if (!mayWrite ||
        (retry
            ? !pending
            : pending ||
                  confirmBody == null ||
                  (hasChanges && !capacityAccepted)))
      return;
    final current = epoch, body = confirmBody, target = confirmPath;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      if (retry) {
        await widget.session.repeatDocumentComponentCommand(widget.eventId);
      } else {
        await freshWrite();
        if (!mounted || current != epoch || !writeRights || pending) return;
        await widget.session.command(key, target!, body!);
      }
      if (!mounted || current != epoch || !mayRead) return;
      await load();
      if (mounted && mayRead)
        setState(
          () => message = 'Belegaufteilung bestätigt. Geldfluss und offene Posten bleiben unverändert.',
        );
    } catch (exception) {
      if (mounted && current == epoch) {
        // A retry is always neutral; private proposals never survive an unknown outcome.
        setState(() {
          preview = confirmBody = null;
          confirmPath = null;
          capacityAccepted = false;
        });
        failure(exception);
        if (mayRead &&
            !pending &&
            exception is ApiException &&
            exception.status == 409) {
          final text = error;
          await load();
          if (mounted && mayRead) setState(() => error = text);
        }
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget heading(String value) =>
      Text(value, style: Theme.of(context).textTheme.titleMedium);
  Widget card(List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final child in children)
            Padding(padding: const EdgeInsets.only(bottom: 8), child: child),
        ],
      ),
    ),
  );
  String money(Map<String, dynamic> value, {String gross = 'gross'}) =>
      'netto ${businessMoney(value['net'])} · ausgewiesene Steuer ${businessMoney(value['tax'])} · brutto ${businessMoney(value[gross])}';
  Widget identity(Map<String, dynamic> group) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading('Beleggruppe · ${'${group['rate']}'.replaceAll('.', ',')} %'),
      Text('Kategorie laut Beleg: ${group['category']}'),
      if (group['reason'] != null && '${group['reason']}'.isNotEmpty)
        Text('${group['reason']}'),
    ],
  );
  Widget portionTitle(Map<String, dynamic> value) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading('${value['number']} · ${value['party_name']}'),
      Text('Ganzer Beleganteil: ${businessMoney(value['amount'])}'),
    ],
  );
  Widget capacityView(Map<String, dynamic> group) {
    final available = businessMap(group['offered_capacity']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        identity(group),
        Text('Laut Originalbeleg: ${money(businessMap(group['archive']))}'),
        Text(
          'Bereits verfügbar: ${money(businessMap(group['current_capacity']))}',
        ),
        Text(
          'Noch nicht übernommene Rücknahmen: ${money(businessMap(group['pending_returns']))}',
        ),
        Text('Für diese Aufteilung angeboten: ${money(available)}'),
        if (available['not_before_date'] != null)
          Text(
            'Frühester Zahlungstag: ${businessDate(available['not_before_date'])}',
          ),
        if (!dateAllowed(available))
          const Text(
            'Für den Zahlungstag dieses Geldflusses noch nicht verwendbar.',
          ),
      ],
    );
  }

  Widget proof(
    Map<String, dynamic> value, {
    required bool historical,
    bool old = false,
  }) {
    final portion = businessMap(value['portion']),
        groups = businessItems(portion['groups']);
    Map<String, dynamic> groupFor(dynamic id) =>
        groups.firstWhere((g) => g['group_id'] == id);
    final changes = businessItems(value['capacity_changes'] ?? []);
    return card([
      heading(
        historical
            ? '${old ? 'Frühere Belegaufteilung' : 'Aufteilung mit wiederverwendbaren Beträgen'} Nr. ${value['revision']}'
            : 'Belegaufteilung prüfen',
      ),
      portionTitle(portion),
      Text('Dokumentierter Anteil: ${money(value, gross: 'amount')}'),
      Text('Begründung: ${value['reason']}'),
      if (!historical && value['action'] != null)
        const Text(
          'Für die hier neu aufgeteilten Zahlungsanteile ist die Zuordnung späterer Erstattungen noch nicht verfügbar.',
        ),
      if (value['action'] == 'takeover_and_document')
        const Text(
          'Alle Gruppen dieser Rechnung werden gemeinsam auf die gezeigten verfügbaren Beträge umgestellt. Künftige Aufteilungen dieser Rechnung verwenden diese fortgeführten Beträge.',
        ),
      for (final change in changes) ...[
        identity(groupFor(change['group_id'])),
        Text('Genauer Übertrag: ${money(businessMap(change['carry']))}'),
        Text(
          'Zusätzlich freizugebende Rücknahmen: ${money(businessMap(change['returned']))}',
        ),
        Text(
          'Gemeinsame verfügbare Basis: ${money(businessMap(change['basis']))}',
        ),
        if (change['not_before_date'] != null)
          Text(
            'Frühester Zahlungstag: ${businessDate(change['not_before_date'])}',
          ),
      ],
      for (final line in businessItems(value['lines'])) ...[
        identity(groupFor(line['group_id'])),
        Text('Dieser Anteil: ${money(line, gross: 'amount')}'),
        Text(
          'Danach noch verfügbar: ${businessMoney(line['remaining_gross'])} brutto',
        ),
      ],
      const Text(
        'Die steuerliche Einordnung bleibt offen. Diese Dokumentation erzeugt keine neue Zahlung und ändert keine offenen Posten.',
      ),
      if (historical)
        Text('Bestätigt: ${businessDate(value['created_at'], time: true)}')
      else ...[
        if (changes.isNotEmpty)
          CheckboxListTile(
            key: const ValueKey('capacity-accept'),
            value: capacityAccepted,
            onChanged: mayWrite
                ? (value) => setState(() => capacityAccepted = value == true)
                : null,
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            title: Text(
              value['action'] == 'takeover_and_document'
                  ? 'Ich bestätige die Übernahme aller Beleggruppen und die gezeigte Freigabe der zurückgenommenen Beträge.'
                  : 'Ich bestätige die gezeigte Freigabe der zurückgenommenen Belegbeträge.',
            ),
          ),
        FilledButton(
          onPressed: mayWrite && (changes.isEmpty || capacityAccepted)
              ? () => confirm()
              : null,
          child: const Text('Belegaufteilung verbindlich bestätigen'),
        ),
        TextButton(
          onPressed: mayWrite
              ? () => setState(() {
                  preview = confirmBody = null;
                  capacityAccepted = false;
                })
              : null,
          child: const Text('Gruppenbeträge ändern'),
        ),
      ],
    ]);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Belegaufteilung'),
      actions: [
        IconButton(
          tooltip: 'Belegaufteilung aktualisieren',
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
            controller: scroll,
            padding: const EdgeInsets.all(24),
            children: [
              const Notice(
                'Hier werden bestätigte Einnahmen auf ihre ursprünglichen Rechnungsgruppen aufgeteilt. Zurückgenommene Beträge werden erst nach ausdrücklicher Prüfung wieder verfügbar. Die steuerliche Einordnung bleibt offen.',
              ),
              if (error != null) Notice(error!, error: true),
              if (message != null) Notice(message!),
              if (loading || busy) const LinearProgressIndicator(),
              if (state != null) ...[
                card([
                  heading(
                    'Bestätigter Geldfluss: ${businessMoney(state!['amount'])}',
                  ),
                  Text('Zahlungstag: ${businessDate(state!['cash_date'])}'),
                  Text(
                    'Insgesamt dokumentiert: ${businessMoney(state!['documented_amount'])} · Noch nicht dokumentiert: ${businessMoney(state!['undocumented_amount'])}',
                  ),
                  Text(
                    'Noch keiner Rechnung zugeordnet: ${businessMoney(state!['unallocated_amount'])}',
                  ),
                  if (state!['eligible'] != true)
                    Text(_blocked(state!['blocked_reason'])),
                  if (!writeRights || state!['writes_allowed'] != true)
                    const Text(
                      'Bestätigte Aufteilungen bleiben lesbar. Neue Aufteilungen sind derzeit gesperrt.',
                    ),
                ]),
                if (pending)
                  card([
                    heading('Unbestätigte Belegaufteilung'),
                    const Text(
                      'Die frühere Übertragung wird zuerst unverändert wiederholt. Gespeicherte Beleg- und Kapazitätsdetails bleiben bis zur aktuellen Prüfung verborgen.',
                    ),
                    FilledButton(
                      onPressed:
                          mayWrite &&
                              widget.session.pendingDocumentComponentPath(
                                    widget.eventId,
                                  ) !=
                                  null
                          ? () => confirm(retry: true)
                          : null,
                      child: const Text('Unverändert erneut senden'),
                    ),
                  ])
                else if (preview != null)
                  proof(preview!, historical: false)
                else if (writeRights && state!['writes_allowed'] == true) ...[
                  if (selected == null) ...[
                    heading('Ganzen Beleganteil auswählen'),
                    for (final portion in portions)
                      card([
                        portionTitle(portion),
                        if (portion['pending_blocked_reason'] != null)
                          Text(_blocked(portion['pending_blocked_reason'])),
                        if (portion['eligible'] == true &&
                            portion['action'] != null)
                          OutlinedButton(
                            onPressed: mayWrite ? () => choose(portion) : null,
                            child: const Text('Diesen Beleganteil aufteilen'),
                          )
                        else
                          Text(_blocked(portion['blocked_reason'])),
                      ]),
                    if (!loading && portions.isEmpty)
                      const Text('Keine offenen Beleganteile verfügbar.'),
                    if (nextPortions != null)
                      OutlinedButton(
                        onPressed: mayWrite ? () => more('portions') : null,
                        child: const Text('Weitere Beleganteile laden'),
                      ),
                  ] else
                    card([
                      portionTitle(selected!),
                      TextButton(
                        onPressed: mayWrite
                            ? () => setState(() {
                                selected = writerPortion = writerState = null;
                              })
                            : null,
                        child: const Text('Anderen Beleganteil auswählen'),
                      ),
                      if (selected!['pending_blocked_reason'] != null)
                        Text(_blocked(selected!['pending_blocked_reason'])),
                      const Text(
                        'Geben Sie die Bruttobeträge ausdrücklich ein. Die Summe muss genau den ganzen Beleganteil ergeben. Leere Felder oder null lassen eine Gruppe aus.',
                      ),
                      for (final group in businessItems(
                        selected!['groups'],
                      )) ...[
                        const Divider(),
                        capacityView(group),
                        if (_cents(
                                  businessMap(
                                    group['offered_capacity'],
                                  )['gross'],
                                ) >
                                BigInt.zero &&
                            dateAllowed(businessMap(group['offered_capacity'])))
                          TextField(
                            key: ValueKey(
                              'capacity-group-${group['group_id']}',
                            ),
                            controller: inputs['${group['group_id']}'],
                            enabled: mayWrite,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            decoration: const InputDecoration(
                              labelText: 'Bruttoanteil dieser Gruppe (€)',
                            ),
                          ),
                      ],
                      TextField(
                        key: const ValueKey('capacity-reason'),
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
                heading('Aufteilungen mit wiederverwendbaren Beträgen'),
                if (!loading && history.isEmpty)
                  const Text(
                    'Noch keine Aufteilung mit wiederverwendbaren Beträgen bestätigt.',
                  ),
                for (final entry in history) proof(entry, historical: true),
                if (nextHistory != null)
                  OutlinedButton(
                    onPressed: loading || busy ? null : () => more('history'),
                    child: const Text('Weitere neue Aufteilungen laden'),
                  ),
                heading('Frühere Belegaufteilungen'),
                if (!loading && legacyHistory.isEmpty)
                  const Text('Keine früheren Belegaufteilungen vorhanden.'),
                for (final entry in legacyHistory)
                  proof(entry, historical: true, old: true),
                if (nextLegacyHistory != null)
                  OutlinedButton(
                    onPressed: loading || busy ? null : () => more('legacy'),
                    child: const Text('Weitere frühere Aufteilungen laden'),
                  ),
              ],
            ],
          ),
  );
}

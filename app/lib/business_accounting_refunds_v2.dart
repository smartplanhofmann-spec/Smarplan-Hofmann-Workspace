import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting.dart'
    show accountingAmount, businessAccountingReadable;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

bool businessVersionedRefundOriginsReadable(BusinessSession session) =>
    businessAccountingReadable(session) &&
    session.hasFeature('accounting_refund_origins_v2') &&
    session.hasModule('accounting_refunds_v2');

String _lotKey(Map<String, dynamic> value) =>
    '${value['origin_version']}:${value['entry_id']}:${value['group_id']}';
BigInt _cents(Object? value) => BigInt.parse('$value'.replaceAll('.', ''));
String _blocked(Object? reason) =>
    const {
      'not_customer_refund': 'Dieser Geldfluss ist keine Kundenerstattung.',
      'source_customer_unresolved':
          'Die Kundenbindung der ursprünglichen Rechnungen ist noch ungeklärt.',
      'unsupported_document': 'Dieser Beleg benötigt eine gesonderte Prüfung.',
      'unallocated': 'Der verbleibende Erstattungsbetrag ist noch keiner Rechnung zugeordnet.',
      'fully_documented':
          'Die Ursprünge dieser Erstattung sind vollständig dokumentiert.',
    }[reason] ??
    'Dieser Erstattungsanteil benötigt eine Klärung.';

class BusinessVersionedRefundOriginsPage extends StatefulWidget {
  const BusinessVersionedRefundOriginsPage({
    super.key,
    required this.session,
    required this.eventId,
  });
  final BusinessSession session;
  final String eventId;
  @override
  State<BusinessVersionedRefundOriginsPage> createState() =>
      _BusinessVersionedRefundOriginsPageState();
}

class _BusinessVersionedRefundOriginsPageState
    extends State<BusinessVersionedRefundOriginsPage> {
  Map<String, dynamic>? state,
      selected,
      writerState,
      writerPortion,
      preview,
      confirmBody;
  List<Map<String, dynamic>> portions = [],
      origins = [],
      history = [],
      legacyHistory = [];
  final inputs = <String, TextEditingController>{};
  final reason = TextEditingController();
  final scroll = ScrollController();
  String? error, message, confirmPath;
  int epoch = 0;
  int? nextPortions, nextOrigins, nextHistory, nextLegacyHistory;
  bool loading = false,
      busy = false,
      denied = false,
      originsVisible = false,
      handoffAccepted = false;
  String get path => '/accounting/refunds/v2/events/${widget.eventId}';
  String get legacyPath => '/accounting/refunds/events/${widget.eventId}';
  String get key => 'accounting-refunds-${widget.eventId}';
  bool get legacy => selected?['action'] == 'bind_legacy';
  String get writerPath => legacy ? legacyPath : path;
  bool get pending => widget.session.pending(key);
  bool get mayRead =>
      businessVersionedRefundOriginsReadable(widget.session) && !denied;
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
    for (final input in inputs.values) {
      input.dispose();
    }
    reason.dispose();
    scroll.dispose();
    super.dispose();
  }

  void clear() {
    epoch++;
    state = selected = writerState = writerPortion = preview = confirmBody =
        null;
    portions = [];
    origins = [];
    history = [];
    legacyHistory = [];
    nextPortions = nextOrigins = nextHistory = nextLegacyHistory = null;
    confirmPath = null;
    loading = busy = originsVisible = handoffAccepted = false;
    for (final input in inputs.values) {
      input.clear();
    }
    reason.clear();
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!businessVersionedRefundOriginsReadable(widget.session)) {
        clear();
      } else if (!writeRights) {
        selected = writerState = writerPortion = preview = confirmBody = null;
        portions = [];
        origins = [];
        originsVisible = handoffAccepted = false;
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
          : 'Die Erstattungsursprünge konnten nicht geladen werden.';
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) scroll.jumpTo(0);
    });
  }

  String? pendingFingerprint() {
    final original = widget.session.pendingRefundOriginPath(widget.eventId);
    return original == null
        ? null
        : jsonEncode({
            'path': original,
            'body': widget.session.pendingCommandValues(key, path: original),
          });
  }

  Future<void> load() async {
    if (!businessVersionedRefundOriginsReadable(widget.session)) return;
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final opening = pendingFingerprint();
      final fresh = businessMap(await widget.session.read(path));
      final original = widget.session.pendingRefundOriginPath(widget.eventId);
      if (original != null && original != '$path/confirm') {
        await widget.session.read(
          original.replaceFirst(RegExp(r'/confirm$'), ''),
        );
      }
      final results = await Future.wait([
        widget.session.read('$path/history?limit=50&offset=0'),
        widget.session.read('$legacyPath/history?limit=50&offset=0'),
        if (!pending &&
            businessVersionedRefundOriginsReadable(widget.session) &&
            widget.session.canWrite('accounting.prepare') &&
            widget.session.canWrite('finance.write') &&
            widget.session.sectionEnabled('finance') &&
            fresh['writes_allowed'] == true &&
            fresh['source_kind'] == 'customer_refund')
          widget.session.read('$path/portions?limit=50&offset=0'),
      ]);
      if (!mounted ||
          current != epoch ||
          !businessVersionedRefundOriginsReadable(widget.session))
        return;
      if (opening != pendingFingerprint()) {
        await load();
        return;
      }
      setState(() {
        denied = false;
        state = fresh;
        history = businessItems(results[0]);
        nextHistory = businessMap(results[0])['next_offset'] as int?;
        legacyHistory = businessItems(results[1]);
        nextLegacyHistory = businessMap(results[1])['next_offset'] as int?;
        portions = results.length == 3 ? businessItems(results[2]) : [];
        nextPortions = results.length == 3
            ? businessMap(results[2])['next_offset'] as int?
            : null;
        selected = writerState = writerPortion = preview = confirmBody = null;
        confirmPath = null;
        origins = [];
        nextOrigins = null;
        originsVisible = handoffAccepted = false;
        for (final input in inputs.values) {
          input.clear();
        }
        reason.clear();
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
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = businessMap(
        await widget.session.read(
          '${collection == 'legacy' ? legacyPath : path}/${collection == 'portions' ? 'portions' : 'history'}?limit=50&offset=$offset',
        ),
      );
      if (!mounted || current != epoch || !mayRead) return;
      setState(() {
        final items = businessItems(result),
            next = result['next_offset'] as int?;
        if (collection == 'portions') {
          portions = [...portions, ...items];
          nextPortions = next;
        } else if (collection == 'legacy') {
          legacyHistory = [...legacyHistory, ...items];
          nextLegacyHistory = next;
        } else {
          history = [...history, ...items];
          nextHistory = next;
        }
      });
    } catch (exception) {
      if (mounted && current == epoch) failure(exception);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<Map<String, dynamic>> findLegacyPortion(String id, int current) async {
    int? offset = 0;
    final visited = <int>{};
    while (offset != null &&
        visited.add(offset) &&
        mounted &&
        current == epoch) {
      final page = businessMap(
        await widget.session.read(
          '$legacyPath/portions?limit=100&offset=$offset',
        ),
      );
      for (final portion in businessItems(page)) {
        if (portion['portion_id'] == id) return portion;
      }
      offset = page['next_offset'] as int?;
    }
    throw const ApiException(
      409,
      'Dieser Erstattungsanteil muss neu geladen werden.',
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
      final old = portion['action'] == 'bind_legacy';
      final fresh = old
          ? businessMap(await widget.session.read(legacyPath))
          : state!;
      final target = old
          ? await findLegacyPortion('${portion['portion_id']}', current)
          : portion;
      if (target['eligible'] != true || target['amount'] != portion['amount']) {
        throw const ApiException(
          409,
          'Der Erstattungsanteil hat sich geändert. Bitte den Stand neu laden.',
        );
      }
      if (!mounted || current != epoch || !writeRights || pending) return;
      setState(() {
        selected = portion;
        writerState = fresh;
        writerPortion = target;
        preview = confirmBody = null;
        confirmPath = null;
        origins = [];
        nextOrigins = null;
        handoffAccepted = originsVisible = false;
        for (final input in inputs.values) {
          input.clear();
        }
        reason.clear();
        busy = false;
      });
      await loadOrigins();
    } catch (exception) {
      if (mounted && current == epoch) failure(exception);
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  // The server's C2 state checks the complete relational source closure, also
  // for C1 origins. Current positive candidates are irrelevant to these rights.
  Future<void> authorizeOrigins(
    List<Map<String, dynamic>> values, {
    bool refreshRefund = true,
  }) async {
    if (refreshRefund) {
      final fresh = businessMap(await widget.session.read(path));
      if (fresh['writes_allowed'] != true)
        throw const ApiException(
          403,
          'Die Erstattungsquelle ist nicht vollständig freigegeben.',
        );
    }
    for (final id in values.map((value) => value['origin_event_id']).toSet()) {
      if (id is! String || !RegExp(r'^[a-f0-9]{32}$').hasMatch(id)) {
        throw const ApiException(
          409,
          'Der Ursprungsnachweis muss neu geladen werden.',
        );
      }
      final source = businessMap(
        await widget.session.read('/accounting/components/v2/events/$id'),
      );
      if (source['writes_allowed'] != true)
        throw const ApiException(
          403,
          'Der Ursprung ist nicht vollständig freigegeben.',
        );
    }
  }

  Future<void> loadOrigins({bool more = false}) async {
    if (!mayWrite ||
        selected == null ||
        pending ||
        (more && nextOrigins == null))
      return;
    final current = ++epoch, offset = more ? nextOrigins! : 0;
    final old = legacy,
        previous = more
            ? List<Map<String, dynamic>>.from(origins)
            : <Map<String, dynamic>>[];
    setState(() {
      loading = true;
      error = null;
      originsVisible = false;
    });
    try {
      if (previous.isNotEmpty) await authorizeOrigins(previous);
      if (!mounted || current != epoch || !writeRights) return;
      final result = businessMap(
        await widget.session.read(
          '$writerPath/origins?portion_id=${writerPortion!['portion_id']}&limit=50&offset=$offset',
        ),
      );
      final values = businessItems(result).map((value) {
        if (!old &&
            value['origin_version'] != 'c1' &&
            value['origin_version'] != 'c2') {
          throw const ApiException(
            409,
            'Die Ursprungsart muss neu geladen werden.',
          );
        }
        return <String, dynamic>{...value, if (old) 'origin_version': 'c1'};
      }).toList();
      if (!mounted || current != epoch || !writeRights || pending) return;
      setState(() {
        origins = <String, Map<String, dynamic>>{
          for (final value in previous) _lotKey(value): value,
          for (final value in values) _lotKey(value): value,
        }.values.toList();
        for (final value in origins) {
          inputs.putIfAbsent(_lotKey(value), TextEditingController.new);
        }
        nextOrigins = result['next_offset'] as int?;
        originsVisible = true;
      });
    } catch (exception) {
      if (mounted && current == epoch) failure(exception);
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
    if (!writeRights)
      throw const ApiException(
        403,
        'Die aktuelle Berechtigung zur Ursprungsbindung fehlt.',
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
    if (!mayWrite || selected == null || !originsVisible || pending) return;
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
      final chosen = <Map<String, dynamic>>[],
          sources = <Map<String, dynamic>>[];
      final old = legacy;
      var total = BigInt.zero;
      for (final origin in origins) {
        final text = inputs[_lotKey(origin)]!.text.trim();
        if (text.isEmpty) continue;
        final decimal = businessDecimal(text);
        if (RegExp(r'^0+(?:\.0{1,2})?$').hasMatch(decimal)) continue;
        final amount = accountingAmount(decimal), cents = _cents(amount);
        if (cents > _cents(origin['remaining_amount']))
          throw const FormatException(
            'Ein Ursprungsbetrag überschreitet den noch rücknehmbaren Bruttobetrag.',
          );
        chosen.add({
          if (!old) 'origin_version': origin['origin_version'],
          'entry_id': origin['entry_id'],
          'group_id': origin['group_id'],
          'lot_state_hash': origin['lot_state_hash'],
          'amount': amount,
        });
        sources.add(origin);
        total += cents;
      }
      if (chosen.isEmpty ||
          chosen.length > 500 ||
          total != _cents(writerPortion!['amount'])) {
        throw const FormatException(
          'Die Ursprungsbeträge müssen zusammen genau den ganzen Erstattungsanteil ergeben.',
        );
      }
      final body = <String, dynamic>{
        'source_hash': writerState!['source_hash'],
        'expected_revision': writerState!['revision'],
        'state_hash': writerState!['state_hash'],
        'portion_id': writerPortion!['portion_id'],
        'portion_state_hash': writerPortion!['portion_state_hash'],
        if (!old) 'action': selected!['action'],
        'origins': chosen,
        'reason': explanation,
      };
      await freshWrite();
      if (!mounted || current != epoch || !writeRights || pending) return;
      await authorizeOrigins(sources, refreshRefund: false);
      if (!mounted || current != epoch || !writeRights || pending) return;
      final proposal = businessMap(
        await (old
            ? widget.session.previewRefundOrigins(widget.eventId, body)
            : widget.session.previewVersionedRefundOrigins(
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
        handoffAccepted = false;
      });
    } catch (exception) {
      if (mounted && current == epoch) failure(exception);
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  Future<void> editOrigins() async {
    if (!mayWrite || pending) return;
    final current = epoch;
    setState(() {
      preview = confirmBody = null;
      confirmPath = null;
      handoffAccepted = false;
      originsVisible = false;
      busy = true;
      error = null;
    });
    try {
      await authorizeOrigins(origins);
      if (!mounted || current != epoch || !writeRights || pending) return;
      setState(() => originsVisible = true);
    } catch (exception) {
      if (mounted && current == epoch) failure(exception);
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  bool get needsHandoff => preview?['action'] == 'takeover_and_bind';
  Future<void> confirm({bool retry = false}) async {
    if (!mayWrite ||
        (retry
            ? !pending
            : pending ||
                  confirmBody == null ||
                  (needsHandoff && !handoffAccepted)))
      return;
    final current = epoch,
        body = confirmBody,
        target = confirmPath,
        proposal = preview;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      if (retry) {
        await widget.session.repeatRefundOriginCommand(widget.eventId);
      } else {
        await freshWrite();
        if (!mounted || current != epoch || !writeRights || pending) return;
        await authorizeOrigins(
          businessItems(proposal!['lines']),
          refreshRefund: false,
        );
        if (!mounted || current != epoch || !writeRights || pending) return;
        await widget.session.command(key, target!, body!);
      }
      if (!mounted || current != epoch || !mayRead) return;
      await load();
      if (mounted && mayRead)
        setState(
          () => message = 'Erstattungsursprung bestätigt. Geldfluss und offene Posten bleiben unverändert.',
        );
    } catch (exception) {
      if (mounted && current == epoch) {
        setState(() {
          preview = confirmBody = null;
          confirmPath = null;
          handoffAccepted = false;
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
  String amounts(
    Map<String, dynamic> value,
    String net,
    String tax,
    String gross,
  ) =>
      'netto ${businessMoney(value[net])} · ausgewiesene Steuer ${businessMoney(value[tax])} · brutto ${businessMoney(value[gross])}';
  Widget portionTitle(Map<String, dynamic> portion) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading('${portion['number']} · ${portion['party_name']}'),
      Text('Ganzer Erstattungsanteil: ${businessMoney(portion['amount'])}'),
    ],
  );
  Widget originIdentity(
    Map<String, dynamic> origin, {
    bool line = false,
  }) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      heading(
        '${origin['origin_version'] == 'c2' ? 'Aufteilung nach Wiederverwendung' : 'Ursprüngliche Aufteilung'} Nr. ${origin['component_sequence']}',
      ),
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
  Widget proof(
    Map<String, dynamic> value, {
    required bool historical,
    bool old = false,
  }) => card([
    heading(
      historical
          ? '${old ? 'Frühere Ursprungsbindung' : 'Erweiterte Ursprungsbindung'} Nr. ${value['revision']}'
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
      'Die steuerliche Einordnung bleibt offen. Diese Ursprungsbindung gibt selbst keine Belegbeträge für neue Aufteilungen frei.',
    ),
    if (historical)
      Text('Bestätigt: ${businessDate(value['created_at'], time: true)}')
    else ...[
      if (needsHandoff) ...[
        const Text(
          'Die gesamte Rechnung verwendet ab jetzt die erweiterte Ursprungsbindung einschließlich wiederverwendeter Zahlungsanteile. Bisherige Bestätigungen bleiben unverändert.',
        ),
        CheckboxListTile(
          key: const ValueKey('refund-v2-handoff'),
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          value: handoffAccepted,
          onChanged: mayWrite
              ? (value) => setState(() => handoffAccepted = value == true)
              : null,
          title: const Text(
            'Ich bestätige die Umstellung der gesamten Rechnung auf diese Ursprungsbindung.',
          ),
        ),
      ],
      FilledButton(
        onPressed: mayWrite && (!needsHandoff || handoffAccepted)
            ? () => confirm()
            : null,
        child: const Text('Erstattungsursprung verbindlich bestätigen'),
      ),
      TextButton(
        onPressed: mayWrite ? editOrigins : null,
        child: const Text('Ursprungsbeträge ändern'),
      ),
    ],
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
                'Hier wird die Herkunft einer bereits erfassten Erstattung dokumentiert. Ursprüngliche und wiederverwendete Zahlungsanteile können ausdrücklich gewählt werden. Es entstehen keine neue Zahlung, keine neue Rechnungszuordnung und kein Steuerergebnis.',
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
                    Text(_blocked(state!['blocked_reason'])),
                  if (!writeRights || state!['writes_allowed'] != true)
                    const Text(
                      'Bestätigte Ursprungsbindungen bleiben lesbar. Neue Bindungen sind derzeit nicht freigegeben.',
                    ),
                ]),
                if (pending)
                  card([
                    heading('Unbestätigte Ursprungsbindung'),
                    const Text(
                      'Die frühere Übertragung wird zuerst unverändert wiederholt. Gespeicherte Ursprungsdetails bleiben bis zur aktuellen Prüfung verborgen.',
                    ),
                    FilledButton(
                      onPressed:
                          mayWrite &&
                              widget.session.pendingRefundOriginPath(
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
                    heading('Ganzen Erstattungsanteil auswählen'),
                    for (final portion in portions)
                      card([
                        portionTitle(portion),
                        if (portion['eligible'] == true &&
                            portion['action'] != null)
                          OutlinedButton(
                            onPressed: mayWrite ? () => choose(portion) : null,
                            child: const Text(
                              'Ursprünge für diesen Anteil wählen',
                            ),
                          )
                        else
                          Text(_blocked(portion['blocked_reason'])),
                      ]),
                    if (!loading && portions.isEmpty)
                      const Text('Keine offenen Erstattungsanteile verfügbar.'),
                    if (nextPortions != null)
                      OutlinedButton(
                        onPressed: mayWrite ? () => more('portions') : null,
                        child: const Text('Weitere Erstattungsanteile laden'),
                      ),
                  ] else
                    card([
                      portionTitle(selected!),
                      TextButton(
                        onPressed: mayWrite
                            ? () => setState(() {
                                selected = writerState = writerPortion = null;
                                origins = [];
                                originsVisible = false;
                              })
                            : null,
                        child: const Text(
                          'Anderen Erstattungsanteil auswählen',
                        ),
                      ),
                      const Text(
                        'Wählen Sie die ursprünglichen Zahlungsanteile ausdrücklich durch einen Bruttobetrag. Die Summe muss genau den ganzen Erstattungsanteil ergeben. Leere Felder oder null lassen einen Ursprung aus.',
                      ),
                      if (originsVisible)
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
                            key: ValueKey(
                              'refund-v2-origin-${_lotKey(origin)}',
                            ),
                            controller: inputs[_lotKey(origin)],
                            enabled: mayWrite,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            decoration: const InputDecoration(
                              labelText: 'Bruttoanteil aus diesem Ursprung (€)',
                            ),
                          ),
                        ],
                      if (!loading && originsVisible && origins.isEmpty)
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
                        key: const ValueKey('refund-v2-reason'),
                        controller: reason,
                        enabled: mayWrite,
                        decoration: const InputDecoration(
                          labelText: 'Begründung der Ursprungsbindung',
                        ),
                      ),
                      OutlinedButton(
                        onPressed:
                            mayWrite && originsVisible && origins.isNotEmpty
                            ? prepare
                            : null,
                        child: const Text('Erstattungsursprung vorschauen'),
                      ),
                    ]),
                ],
                const SizedBox(height: 16),
                heading('Erweiterte Ursprungsbindungen'),
                if (!loading && history.isEmpty)
                  const Text(
                    'Noch keine erweiterte Ursprungsbindung bestätigt.',
                  ),
                for (final entry in history) proof(entry, historical: true),
                if (nextHistory != null)
                  OutlinedButton(
                    onPressed: loading || busy ? null : () => more('history'),
                    child: const Text(
                      'Weitere erweiterte Ursprungsbindungen laden',
                    ),
                  ),
                heading('Frühere Ursprungsbindungen'),
                if (!loading && legacyHistory.isEmpty)
                  const Text('Keine früheren Ursprungsbindungen vorhanden.'),
                for (final entry in legacyHistory)
                  proof(entry, historical: true, old: true),
                if (nextLegacyHistory != null)
                  OutlinedButton(
                    onPressed: loading || busy ? null : () => more('legacy'),
                    child: const Text(
                      'Weitere frühere Ursprungsbindungen laden',
                    ),
                  ),
              ],
            ],
          ),
  );
}

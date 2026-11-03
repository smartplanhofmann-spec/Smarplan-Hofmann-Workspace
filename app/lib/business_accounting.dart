import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting_allocations.dart';
import 'business_accounting_components.dart';
import 'business_accounting_refunds.dart';
import 'business_accounting_refunds_v2.dart';
import 'business_accounting_capacity.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

bool businessAccountingReadable(BusinessSession session) =>
    session.projectId == null &&
    session.hasFeature('accounting_prejournal') &&
    session.hasModule('accounting') &&
    session.can('accounting.read') &&
    session.can('finance.read');

/// Exact cents: no binary floats and no rounding of extra decimal places.
String accountingAmount(String input) {
  final value = businessDecimal(input);
  if (!RegExp(r'^\d{1,9}(?:\.\d{1,2})?$').hasMatch(value)) {
    throw const FormatException(
      'Bitte einen EUR-Betrag mit höchstens zwei Nachkommastellen eingeben.',
    );
  }
  final parts = value.split('.');
  final cents =
      int.parse(parts[0]) * 100 +
      int.parse((parts.length == 2 ? parts[1] : '').padRight(2, '0'));
  if (cents <= 0)
    throw const FormatException('Der Betrag muss größer als null sein.');
  return '${cents ~/ 100}.${(cents % 100).toString().padLeft(2, '0')}';
}

String accountingCashDate(String input) {
  final text = input.trim();
  final iso = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$').firstMatch(text);
  final local = RegExp(r'^(\d{1,2})\.(\d{1,2})\.(\d{4})$').firstMatch(text);
  if (iso == null && local == null) {
    throw const FormatException(
      'Bitte den Geldflusstag als TT.MM.JJJJ oder JJJJ-MM-TT eingeben.',
    );
  }
  final year = int.parse(iso?[1] ?? local![3]!);
  final month = int.parse(iso?[2] ?? local![2]!);
  final day = int.parse(iso?[3] ?? local![1]!);
  final date = DateTime.utc(year, month, day);
  if (year < 1 ||
      year > 9999 ||
      date.year != year ||
      date.month != month ||
      date.day != day) {
    throw const FormatException(
      'Der Geldflusstag ist kein gültiger Kalendertag.',
    );
  }
  return '${year.toString().padLeft(4, '0')}-${month.toString().padLeft(2, '0')}-${day.toString().padLeft(2, '0')}';
}

const _accountKinds = {
  'bank': 'Bankkonto',
  'cash': 'Kasse',
  'payment_service': 'Zahlungsdienst',
};
const _tabs = {
  'events': 'Vorjournal',
  'payments': 'Kundenzahlungen',
  'receipts': 'Auszahlungen',
  'accounts': 'Geldkonten',
};
const _blockedReasons = {
  'review_changed': 'Die Belegprüfung wurde geändert. Weitere Auszahlungen benötigen eine Klärung.',
  'duplicate_original':
      'Dieses Original ist bereits anderweitig zahlungsgebunden. Bitte klären.',
  'paid': 'Dieser Beleg ist vollständig ausgezahlt.',
};

class BusinessAccountingPage extends StatefulWidget {
  const BusinessAccountingPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessAccountingPage> createState() => _BusinessAccountingPageState();
}

class _BusinessAccountingPageState extends State<BusinessAccountingPage> {
  String tab = 'events';
  List<Map<String, dynamic>> accounts = [], items = [];
  Map<String, dynamic>? status, event;
  String? error;
  bool loading = false, denied = false;
  int epoch = 0;
  int? nextOffset;
  bool get mayRead => businessAccountingReadable(widget.session) && !denied;
  bool mayWrite(String right) =>
      mayRead &&
      !loading &&
      widget.session.error == null &&
      widget.session.canWrite(right) &&
      widget.session.sectionEnabled('finance') &&
      status?['writes_allowed'] == true;
  String get collection =>
      tab == 'events' ? '/accounting/events' : '/accounting/sources/$tab';

  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void clear() {
    epoch++;
    accounts = [];
    items = [];
    status = event = null;
    nextOffset = null;
    loading = false;
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!businessAccountingReadable(widget.session)) clear();
    });
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load({bool more = false}) async {
    if (!businessAccountingReadable(widget.session)) return;
    final current = ++epoch;
    final offset = more ? nextOffset : 0;
    if (offset == null) return;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = await Future.wait([
        widget.session.read('/accounting/status'),
        widget.session.read('/accounting/accounts'),
        if (tab != 'accounts')
          widget.session.read('$collection?limit=50&offset=$offset'),
      ]);
      if (!mounted ||
          current != epoch ||
          !businessAccountingReadable(widget.session))
        return;
      setState(() {
        denied = false;
        status = businessMap(result[0]);
        accounts = businessItems(result[1]);
        if (tab != 'accounts') {
          final page = businessMap(result[2]);
          items = [if (more) ...items, ...businessItems(page)];
          nextOffset = page['next_offset'] as int?;
        } else {
          items = [];
          nextOffset = null;
        }
      });
    } catch (e) {
      if (!mounted || current != epoch) return;
      setState(() {
        if (e is ApiException && [401, 403, 404].contains(e.status)) {
          clear();
          denied = true;
        }
        error = '$e';
      });
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> freshWrite(String right) async {
    try {
      await _freshWrite(right);
    } on ApiException catch (e) {
      accessFailure(e);
      rethrow;
    }
  }

  void accessFailure(ApiException e) {
    if (mounted && [401, 403, 404].contains(e.status)) {
      setState(() {
        clear();
        denied = true;
        error = e.message;
      });
    }
  }

  Future<void> _freshWrite(String right) async {
    await widget.session.load();
    if (widget.session.error != null || widget.session.loading) {
      throw const ApiException(
        0,
        'Die aktuellen Rechte konnten noch nicht bestätigt werden.',
      );
    }
    if (!mayRead || !widget.session.canWrite(right)) {
      throw const ApiException(
        403,
        'Die aktuellen globalen Fachrechte erlauben diesen Vorgang nicht.',
      );
    }
    if (!widget.session.sectionEnabled('finance')) {
      throw const ApiException(
        423,
        'Finanzen ist fachlich deaktiviert. Der gespeicherte Stand bleibt lesbar.',
      );
    }
    final fresh = businessMap(await widget.session.read('/accounting/status'));
    if (!mayRead || !widget.session.canWrite(right)) {
      throw const ApiException(
        403,
        'Die Berechtigung ist nicht mehr verfügbar.',
      );
    }
    if (fresh['writes_allowed'] != true) {
      throw const ApiException(
        423,
        'Neue Bestätigungen sind bis zum Betreiberabgleich gesperrt.',
      );
    }
  }

  Future<void> send(
    String key,
    String path,
    Map<String, dynamic> values,
  ) async {
    try {
      await widget.session.command(key, path, values);
    } on ApiException catch (e) {
      // A project/source denial can be more specific than global capabilities.
      // Once known, neither the page nor its open editor may retain that data.
      accessFailure(e);
      rethrow;
    }
  }

  void confirm(Map<String, dynamic> values) {
    if (values['confirmation'] != true) {
      throw const FormatException(
        'Bitte die ausdrückliche Bestätigung aktivieren.',
      );
    }
  }

  void requirePendingContinuation(
    Map<String, dynamic>? openedPending,
    Map<String, dynamic>? currentPending,
  ) {
    if (openedPending != null && currentPending == null) {
      throw const ApiException(
        409,
        'Die frühere Übertragung wurde inzwischen beantwortet. Bitte schließen '
        'Sie dieses Formular und prüfen Sie den gespeicherten Stand, bevor '
        'Sie einen neuen Vorgang beginnen.',
      );
    }
  }

  String textValue(
    Map<String, dynamic> values,
    String key,
    int max, {
    bool required = true,
  }) {
    final text = '${values[key] ?? ''}'.trim();
    if ((required && text.isEmpty) || text.length > max) {
      throw FormatException(
        'Bitte eine gültige Angabe mit ${required ? '1' : '0'} bis $max Zeichen eingeben.',
      );
    }
    if (RegExp(r'[\x00-\x1f\x7f]').hasMatch(text)) {
      throw const FormatException(
        'Bitte einzeiligen Text ohne Steuerzeichen eingeben.',
      );
    }
    return text;
  }

  Future<void> editAccount([Map<String, dynamic>? account]) async {
    if (!mayWrite('accounting.admin')) return;
    final session = widget.session;
    final path = account == null
        ? '/accounting/accounts'
        : '/accounting/accounts/${account['id']}';
    final key = 'accounting-account-${account?['id'] ?? 'new'}';
    final pending = session.pendingCommandValues(key, path: path);
    if (pending != null && session.pendingEditorValues(key) == null) {
      session.preservePendingEditor(key, pending);
    }
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        pendingKey: key,
        readAllowed: () => mayRead,
        readPermission: 'accounting.read',
        writePermission: 'accounting.admin',
        title: account == null ? 'Geldkonto anlegen' : 'Geldkonto ändern',
        initial: account ?? const {},
        fields: [
          if (account == null) ...[
            const BusinessField(
              'code',
              'Stabiler Kontocode',
              required: true,
              hint: 'Buchstaben, Ziffern, _ oder -',
            ),
            const BusinessField(
              'kind',
              'Kontoart',
              type: BusinessInput.choice,
              required: true,
              choices: _accountKinds,
            ),
          ],
          const BusinessField('name', 'Kontobezeichnung', required: true),
          if (account != null)
            const BusinessField(
              'active',
              'Für neue Geldflüsse aktiv',
              type: BusinessInput.toggle,
            ),
          const BusinessField(
            'confirmation',
            'Ich bestätige dieses EUR-Geldkonto. Es wird keine Bankverbindung hergestellt.',
            type: BusinessInput.toggle,
          ),
        ],
        onSave: (values) async {
          confirm(values);
          final previous = session.pendingCommandValues(key, path: path);
          requirePendingContinuation(pending, previous);
          final name = textValue(values, 'name', 200);
          final code = account == null ? textValue(values, 'code', 40) : null;
          if (code != null && !RegExp(r'^[A-Za-z0-9_-]+$').hasMatch(code)) {
            throw const FormatException(
              'Der Kontocode darf nur Buchstaben, Ziffern, _ und - enthalten.',
            );
          }
          await freshWrite('accounting.admin');
          requirePendingContinuation(
            pending ?? previous,
            session.pendingCommandValues(key, path: path),
          );
          await send(
            key,
            path,
            previous ??
                {
                  if (account == null) ...{
                    'code': code,
                    'kind': values['kind'],
                  },
                  if (account != null) ...{
                    'revision': account['revision'],
                    'active': values['active'],
                  },
                  'name': name,
                  'confirmation': true,
                },
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> capture(
    Map<String, dynamic> source, {
    required bool payout,
  }) async {
    if (!mayWrite('accounting.prepare')) return;
    final session = widget.session;
    final id = source[payout ? 'receipt_id' : 'payment_id'];
    final path = '/accounting/events/${payout ? 'payout' : 'import-payment'}';
    final key = 'accounting-${payout ? 'payout' : 'payment'}-$id';
    final pending = session.pendingCommandValues(key, path: path);
    if (pending != null && session.pendingEditorValues(key) == null) {
      // A dialog can be reopened before the first request has returned. Its
      // immutable command already owns these fields even before any error.
      session.preservePendingEditor(key, pending);
    }
    final choices = <String, String>{
      for (final account in accounts.where((a) => a['active'] == true))
        '${account['id']}': '${account['code']} · ${account['name']} · EUR',
      if (pending != null)
        '${pending['account_id']}':
            'Bestätigtes Konto · Revision ${pending['account_revision']} (noch unbestätigte Übertragung)',
    };
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        pendingKey: key,
        readAllowed: () => mayRead,
        readPermission: 'accounting.read',
        writePermission: 'accounting.prepare',
        title: payout
            ? 'Auszahlung bestätigen'
            : 'Vorhandene Zahlung übernehmen',
        saveLabel: payout
            ? 'Geldabfluss bestätigen'
            : 'Einmalig ins Vorjournal übernehmen',
        fields: [
          BusinessField(
            'account_id',
            'EUR-Geldkonto',
            type: BusinessInput.choice,
            required: true,
            choices: choices,
          ),
          if (payout)
            BusinessField(
              'amount',
              'Bestätigter Geldabfluss (€)',
              type: BusinessInput.decimal,
              required: true,
              hint: 'Offen: ${businessMoney(source['remaining_amount'])}',
            ),
          const BusinessField(
            'cash_date',
            'Bestätigter Geldflusstag',
            hint: 'TT.MM.JJJJ oder JJJJ-MM-TT',
            required: true,
          ),
          const BusinessField(
            'evidence_reference',
            'Eindeutige Nachweisreferenz auf diesem Konto',
            required: true,
          ),
          if (payout) const BusinessField('reference', 'Verwendungszweck'),
          BusinessField(
            'confirmation',
            payout
                ? 'Ich bestätige den tatsächlich erfolgten EUR-Geldabfluss auf diesen geprüften Beleg. Es wird keine Überweisung ausgelöst.'
                : 'Ich bestätige Konto und Geldflusstag dieser vorhandenen Zahlung. Es wird keine neue Kundenzahlung angelegt.',
            type: BusinessInput.toggle,
          ),
        ],
        onSave: (values) async {
          confirm(values);
          final previous = session.pendingCommandValues(key, path: path);
          requirePendingContinuation(pending, previous);
          final account = accounts
              .where((a) => a['id'] == values['account_id'])
              .firstOrNull;
          if (previous == null &&
              (account == null || account['active'] != true)) {
            throw const FormatException(
              'Bitte ein aktives EUR-Geldkonto wählen.',
            );
          }
          final amount = payout
              ? accountingAmount('${values['amount']}')
              : null;
          if (previous == null &&
              payout &&
              int.parse(amount!.replaceAll('.', '')) >
                  int.parse(
                    '${source['remaining_amount']}'.replaceAll('.', ''),
                  )) {
            throw const FormatException(
              'Der Geldabfluss überschreitet den verbleibenden Belegbetrag.',
            );
          }
          final evidence = textValue(values, 'evidence_reference', 200);
          final cashDate = accountingCashDate('${values['cash_date']}');
          final reference = payout
              ? textValue(values, 'reference', 1000, required: false)
              : null;
          await freshWrite('accounting.prepare');
          requirePendingContinuation(
            pending ?? previous,
            session.pendingCommandValues(key, path: path),
          );
          await send(
            key,
            path,
            previous ??
                {
                  payout ? 'receipt_id' : 'payment_id': id,
                  'source_hash': source['source_hash'],
                  if (payout) ...{
                    'review_revision': source['review_revision'],
                    'review_sha256': source['review_sha256'],
                    'original_sha256': source['original_sha256'],
                    'expected_cash_revision': source['cash_revision'],
                    'amount': amount,
                    'reference': reference,
                  },
                  'account_id': account!['id'],
                  'account_revision': account['revision'],
                  'cash_date': cashDate,
                  'evidence_reference': evidence,
                  'confirmation': true,
                },
          );
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> openEvent(String id) async {
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
      event = null;
    });
    try {
      final result = businessMap(
        await widget.session.read('/accounting/events/$id'),
      );
      if (mounted && current == epoch && mayRead)
        setState(() => event = result);
    } catch (e) {
      if (mounted && current == epoch)
        setState(() {
          if (e is ApiException && [401, 403, 404].contains(e.status)) {
            clear();
            denied = true;
          }
          error = '$e';
        });
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> openAllocations(String paymentId) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => BusinessPaymentAllocationsPage(
          session: widget.session,
          paymentId: paymentId,
        ),
      ),
    );
    if (!mounted) return;
    setState(() => event = null);
    await load();
  }

  Future<void> openComponents(String eventId, {bool reusable = false}) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => reusable && businessCapacityReadable(widget.session)
            ? BusinessReusableComponentsPage(
                session: widget.session,
                eventId: eventId,
              )
            : BusinessDocumentComponentsPage(
                session: widget.session,
                eventId: eventId,
              ),
      ),
    );
    if (!mounted) return;
    setState(() => event = null);
    await load();
  }

  Future<void> openRefundOrigins(String eventId) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => businessVersionedRefundOriginsReadable(widget.session)
            ? BusinessVersionedRefundOriginsPage(
                session: widget.session,
                eventId: eventId,
              )
            : BusinessRefundOriginsPage(
                session: widget.session,
                eventId: eventId,
              ),
      ),
    );
    if (!mounted) return;
    setState(() => event = null);
    await load();
  }

  Widget allocationEntry(String paymentId) => TextButton(
    onPressed: () => openAllocations(paymentId),
    child: Text(
      widget.session.canWrite('accounting.prepare') &&
              widget.session.canWrite('finance.write') &&
              widget.session.sectionEnabled('finance')
          ? 'Rechnung zuordnen'
          : 'Zuordnungen ansehen',
    ),
  );

  Widget card(List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children
            .map(
              (child) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: child,
              ),
            )
            .toList(),
      ),
    ),
  );
  Widget heading(String text) =>
      Text(text, style: Theme.of(context).textTheme.titleMedium);

  Widget eventCard(Map<String, dynamic> value, {bool detail = false}) {
    final account = businessMap(value['account']);
    final source = businessMap(value['source']);
    final snapshot = businessMap(source['snapshot']);
    return card([
      heading(
        'Nr. ${value['sequence']} · ${value['direction'] == 'in' ? 'Eingang' : 'Ausgang'} · ${businessMoney(value['amount'])}',
      ),
      Text('Geldflusstag: ${businessDate(value['cash_date'])}'),
      Text(
        '${account['code']} · ${account['name']} · Kontoversion ${account['revision']}',
      ),
      Text('Nachweis: ${value['evidence_reference']}'),
      if ('${value['reference'] ?? ''}'.isNotEmpty)
        Text('Verwendungszweck: ${value['reference']}'),
      const Text('Steuerliche Einordnung: offen'),
      if ((value['unresolved_reasons'] as List? ?? []).contains(
        'refund_origin_unresolved',
      ))
        Text(
          businessRefundOriginsReadable(widget.session)
              ? 'Bei der Übernahme war der Erstattungsursprung ungeklärt. Spätere Ursprungsbindungen stehen in der eigenen Historie.'
              : 'Der ursprüngliche Erstattungsbezug ist noch ungeklärt.',
        ),
      if (detail) ...[
        Text('Erfasst: ${businessDate(value['created_at'], time: true)}'),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('Historischer Quellennachweis bei Übernahme'),
          children: [
            SelectableText(
              'Quelle: ${source['kind'] == 'payment' ? 'Bestätigte Kundenzahlung' : 'Geprüfter Eingangsbeleg'}\nID: ${source['id']}\nSHA-256: ${source['source_hash']}',
            ),
            if (source['kind'] == 'receipt') ...[
              Text(
                '${snapshot['vendor']} · ${snapshot['invoice_number']} · ${snapshot['filename']}',
              ),
              Text(
                'Prüfung ${snapshot['review_revision']} · Brutto ${businessMoney(snapshot['gross'])}',
              ),
              SelectableText(
                'Original: ${snapshot['original_sha256']}\nPrüfung: ${snapshot['review_sha256']}',
              ),
            ] else ...[
              Text(
                'Ursprünglicher Buchungstag: ${businessDate(snapshot['booking_date'])}',
              ),
              Text(
                'Quelle: ${snapshot['reference']} · Nicht zugeordnet: ${businessMoney(snapshot['unallocated'])}',
              ),
              for (final allocation in businessItems(
                snapshot['allocations'] ?? [],
              ))
                Text(
                  '${allocation['number']} · ${businessMoney(allocation['amount'])}',
                ),
            ],
          ],
        ),
        if (source['kind'] == 'payment' &&
            snapshot['kind'] == 'receipt' &&
            businessAllocationsReadable(widget.session))
          allocationEntry('${source['id']}'),
        if (source['kind'] == 'payment' &&
            snapshot['kind'] == 'refund' &&
            businessRefundOriginsReadable(widget.session))
          TextButton(
            onPressed: () => openRefundOrigins('${value['id']}'),
            child: const Text('Erstattungsursprünge ansehen'),
          )
        else if (businessComponentsReadable(widget.session))
          TextButton(
            onPressed: () => openComponents(
              '${value['id']}',
              reusable:
                  source['kind'] == 'payment' && snapshot['kind'] == 'receipt',
            ),
            child: Text(
              widget.session.canWrite('accounting.prepare') &&
                      widget.session.canWrite('finance.write') &&
                      widget.session.sectionEnabled('finance') &&
                      snapshot['kind'] != 'refund'
                  ? 'Beleganteile aufteilen'
                  : 'Aufteilungen ansehen',
            ),
          ),
      ] else
        TextButton(
          onPressed: () => openEvent('${value['id']}'),
          child: const Text('Geldfluss ansehen'),
        ),
    ]);
  }

  Widget paymentCard(Map<String, dynamic> source) {
    final pending = widget.session.pending(
      'accounting-payment-${source['payment_id']}',
    );
    return card([
      heading(
        '${source['kind'] == 'refund' ? 'Erstattung' : 'Kundenzahlung'} · ${businessMoney(source['amount'])}',
      ),
      Text(
        'Buchungstag: ${businessDate(source['booking_date'])} · ${source['reference']}',
      ),
      for (final allocation in businessItems(source['allocations'] ?? []))
        Text(
          '${allocation['number']} · ${businessMoney(allocation['amount'])}',
        ),
      Text(
        '${source['linked_event_id'] != null && businessAllocationsReadable(widget.session) ? 'Im ursprünglichen Zahlungsnachweis nicht zugeordnet' : 'Nicht zugeordnet'}: ${businessMoney(source['unallocated'])}',
      ),
      if (source['linked_event_id'] != null)
        TextButton(
          onPressed: () => openEvent('${source['linked_event_id']}'),
          child: const Text('Bereits im Vorjournal · ansehen'),
        ),
      if (source['linked_event_id'] != null &&
          source['kind'] == 'receipt' &&
          businessAllocationsReadable(widget.session))
        allocationEntry('${source['payment_id']}'),
      if (mayWrite('accounting.prepare') &&
          (source['linked_event_id'] == null || pending))
        OutlinedButton(
          onPressed: () => capture(source, payout: false),
          child: Text(pending ? 'Übernahme fortsetzen' : 'Zahlung übernehmen'),
        ),
    ]);
  }

  Widget receiptCard(Map<String, dynamic> source) {
    final pending = widget.session.pending(
      'accounting-payout-${source['receipt_id']}',
    );
    return card([
      heading('${source['vendor']} · ${source['invoice_number']}'),
      Text(
        '${source['filename']} · Belegdatum ${businessDate(source['issue_date'])} · Prüfung ${source['review_revision']}',
      ),
      Text('Beleg brutto: ${businessMoney(source['gross'])}'),
      Text(
        'Bestätigt ausgezahlt: ${businessMoney(source['paid_amount'])} · Verbleibend: ${businessMoney(source['remaining_amount'])}',
      ),
      if (source['payable'] != true)
        Text(
          _blockedReasons[source['blocked_reason']] ??
              'Weitere Auszahlungen benötigen eine Klärung.',
        ),
      if (mayWrite('accounting.prepare') &&
          (source['payable'] == true || pending))
        OutlinedButton(
          onPressed: () => capture(source, payout: true),
          child: Text(
            pending ? 'Auszahlung fortsetzen' : 'Auszahlung bestätigen',
          ),
        ),
    ]);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('EÜR-Vorbereitung'),
      actions: [
        IconButton(
          tooltip: 'Vorjournal aktualisieren',
          onPressed: loading
              ? null
              : () {
                  setState(() => event = null);
                  load();
                },
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !mayRead
        ? BusinessEmpty(
            'EÜR-Vorbereitung nicht freigegeben',
            error ?? 'Dieser Bereich benötigt globale Finanz- und EÜR-Leserechte sowie die Serverfreigabe.',
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Notice(
                'Steuerprofil nicht eingerichtet. Dieses Vorjournal enthält belegte Geldflüsse ohne steuerliche Einordnung. Ein EÜR-Ergebnis ist noch nicht verfügbar.',
              ),
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('Nur freigegebene Quellen · ohne Projektfilter'),
              ),
              if (error != null) Notice(error!, error: true),
              if (loading) const LinearProgressIndicator(),
              if (status != null &&
                  (!widget.session.sectionEnabled('finance') ||
                      widget.session.readonly ||
                      status!['writes_allowed'] != true))
                const Notice(
                  'Der gespeicherte Stand ist lesbar. Neue Bestätigungen sind derzeit gesperrt.',
                ),
              if (event != null) ...[
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () => setState(() => event = null),
                    icon: const Icon(Icons.arrow_back),
                    label: const Text('Zur Übersicht'),
                  ),
                ),
                eventCard(event!, detail: true),
              ] else ...[
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final entry in _tabs.entries)
                      ChoiceChip(
                        label: Text(entry.value),
                        selected: tab == entry.key,
                        onSelected: loading
                            ? null
                            : (_) {
                                setState(() {
                                  tab = entry.key;
                                  items = [];
                                  nextOffset = null;
                                });
                                load();
                              },
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                if (tab == 'accounts') ...[
                  const Text(
                    'Manuell bestätigte EUR-Geldkonten. Es besteht keine Bankanbindung.',
                  ),
                  if (mayWrite('accounting.admin'))
                    Align(
                      alignment: Alignment.centerLeft,
                      child: OutlinedButton.icon(
                        onPressed: () => editAccount(),
                        icon: const Icon(Icons.add),
                        label: const Text('Geldkonto anlegen'),
                      ),
                    ),
                  for (final account in accounts)
                    card([
                      heading('${account['code']} · ${account['name']}'),
                      Text(
                        '${_accountKinds[account['kind']] ?? account['kind']} · EUR · Revision ${account['revision']} · ${account['active'] == true ? 'Aktiv' : 'Inaktiv'}',
                      ),
                      if (mayWrite('accounting.admin'))
                        TextButton(
                          onPressed: () => editAccount(account),
                          child: const Text('Konto ändern'),
                        ),
                    ]),
                ] else ...[
                  if (tab == 'payments')
                    const Text(
                      'Vorhandene bestätigte Kundenzahlungen werden einmalig verknüpft. Offene Posten bleiben unverändert.',
                    ),
                  if (tab == 'receipts')
                    const Text(
                      'Nur tatsächlich erfolgte Auszahlungen auf geprüfte EUR-Belege bestätigen. Es wird keine Überweisung ausgelöst.',
                    ),
                  if (tab != 'events' &&
                      accounts.every((a) => a['active'] != true))
                    const Notice(
                      'Für neue Geldflüsse muss zuerst ein berechtigter Benutzer ein aktives EUR-Geldkonto anlegen.',
                    ),
                  for (final item in items)
                    switch (tab) {
                      'payments' => paymentCard(item),
                      'receipts' => receiptCard(item),
                      _ => eventCard(item),
                    },
                  if (!loading && items.isEmpty && error == null)
                    const BusinessEmpty(
                      'Keine Einträge',
                      'Für Ihren Zugriffsbereich liegen in dieser Ansicht keine Einträge vor.',
                    ),
                  if (nextOffset != null)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: OutlinedButton(
                        onPressed: loading ? null : () => load(more: true),
                        child: const Text('Weitere Einträge laden'),
                      ),
                    ),
                ],
              ],
            ],
          ),
  );
}

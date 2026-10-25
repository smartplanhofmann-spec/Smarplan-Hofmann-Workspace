import 'package:flutter/material.dart';

import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;

class BusinessFinancePage extends StatefulWidget {
  const BusinessFinancePage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessFinancePage> createState() => _BusinessFinancePageState();
}

class _BusinessFinancePageState extends State<BusinessFinancePage> {
  List<Map<String, dynamic>> items = [], outbox = [], proposals = [];
  String? error, message;
  bool loading = true, busy = false;
  int epoch = 0;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (!mounted) return;
    if (!widget.session.can('finance.read')) {
      epoch++;
      items = [];
      outbox = [];
      proposals = [];
    }
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    final current = ++epoch;
    setState(() => loading = true);
    try {
      final list = businessItems(
        await widget.session.read(widget.session.query('/finance/open-items')),
      );
      final deliveries = businessItems(
        await widget.session.read('/finance/outbox'),
      );
      if (mounted && current == epoch && widget.session.can('finance.read'))
        setState(() {
          items = list;
          outbox = deliveries;
        });
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> payment(Map<String, dynamic> item) async {
    final source = 'manual-${offlineId()}';
    final key = 'payment-$source';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Zahlung zu ${item['number']} erfassen',
        fields: const [
          BusinessField(
            'amount',
            'Zahlungseingang (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'booking_date',
            'Buchungsdatum',
            type: BusinessInput.date,
            required: true,
          ),
          BusinessField(
            'reference',
            'Buchungshinweis / Belegreferenz',
            required: true,
          ),
        ],
        initial: {
          'amount': item['open'],
          'booking_date': DateTime.now().toIso8601String().substring(0, 10),
        },
        onSave: (values) async {
          await widget.session.command(key, '/finance/payments', {
            'source_id': source,
            'kind': 'receipt',
            'currency': 'EUR',
            ...values,
            'allocations': [
              {
                'document_id': item['document_id'] ?? item['id'],
                'amount': values['amount'],
              },
            ],
          });
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> prepare() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
      message = null;
    });
    try {
      final result = businessItems(
        await widget.session.command(
          'dunning-preview',
          '/finance/dunning/preview',
          {
            if (widget.session.projectId != null)
              'project_id': widget.session.projectId,
          },
        ),
      );
      if (mounted && widget.session.can('finance.read'))
        setState(() => proposals = result);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> approve(Map<String, dynamic> proposal) async {
    if (busy || !widget.session.canWrite('finance.approve')) return;
    if (!await businessConfirm(
          context,
          title: 'Diese Mahnung freigeben?',
          message: 'Bitte prüfen Sie Empfänger, Betrag und Text. Die Freigabe gilt für genau diese Fassung. Ein nicht eingerichteter Versand wird nicht als zugestellt gemeldet.',
          action: 'Geprüfte Fassung freigeben',
        ) ||
        !mounted)
      return;
    setState(() => busy = true);
    try {
      final result = businessMap(
        await widget.session.command(
          'dunning-approve-${proposal['id']}',
          '/finance/dunning/proposals/${proposal['id']}/approve',
          {'confirmation': true},
        ),
      );
      if (mounted && widget.session.can('finance.read')) {
        setState(() {
          proposals.removeWhere((p) => p['id'] == proposal['id']);
          message = result['sent'] == true
              ? 'Vom Mailserver angenommen; der Empfang ist nicht bestätigt.'
              : 'Freigabe gespeichert. Die Zustellung ist noch nicht bestätigt.';
        });
        await load();
      }
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.can('finance.read'))
      return const BusinessEmpty(
        'Finanzen nicht freigegeben',
        'Für diesen Bereich benötigen Sie Finanzrechte.',
        icon: Icons.lock_outline,
      );
    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Wrap(
            spacing: 16,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                'Finanzen',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              if (widget.session.canWrite('finance.write'))
                OutlinedButton.icon(
                  onPressed: busy ? null : prepare,
                  icon: const Icon(Icons.rule_outlined),
                  label: const Text('Mahnlauf vorbereiten'),
                ),
            ],
          ),
          const SizedBox(height: 12),
          const Notice(
            'Mahnungen werden zuerst vorgeschlagen. Ohne ausdrückliche Freigabe wird nichts versendet. Zahlungen sind bestätigte Buchungen und keine bloßen Statusänderungen.',
          ),
          if (error != null) Notice(error!, error: true),
          if (message != null) Notice(message!),
          if (loading || busy) const LinearProgressIndicator(),
          const SizedBox(height: 16),
          Text('Offene Posten', style: Theme.of(context).textTheme.titleLarge),
          if (!loading && items.isEmpty && error == null)
            const BusinessEmpty(
              'Keine offenen Posten',
              'Für Ihren Zugriffsbereich liegen keine offenen Rechnungsbeträge vor.',
            ),
          for (final item in items)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${item['number']}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Offen: ${businessMoney(item['open'])} · Gebucht: ${businessMoney(item['paid'])}',
                    ),
                    Text(
                      'Fällig: ${businessDate(item['due_date'])} · Mahnstufe ${item['level'] ?? 0}',
                    ),
                    if (item['blocked_by_delivery'] == true)
                      const Text(
                        'Zustellstatus vor dem nächsten Mahnschritt klären.',
                      ),
                    if (widget.session.canWrite('finance.write'))
                      TextButton.icon(
                        onPressed: busy ? null : () => payment(item),
                        icon: const Icon(Icons.add_card_outlined),
                        label: const Text('Zahlung erfassen'),
                      ),
                  ],
                ),
              ),
            ),
          if (proposals.isNotEmpty) ...[
            const SizedBox(height: 24),
            Text(
              'Vorschläge prüfen',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            for (final p in proposals)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${p['rule']?['name'] ?? 'Mahnung'} · ${p['number'] ?? ''}',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text('Empfänger: ${p['recipient'] ?? 'Nicht angegeben'}'),
                      Text('Betrag: ${businessMoney(p['total'] ?? p['open'])}'),
                      const SizedBox(height: 12),
                      Text('${p['rule']?['subject'] ?? ''}'),
                      Text('${p['rule']?['text'] ?? ''}'),
                      const SizedBox(height: 12),
                      if (widget.session.canWrite('finance.approve'))
                        FilledButton(
                          onPressed: busy ? null : () => approve(p),
                          child: const Text('Fassung prüfen und freigeben'),
                        ),
                    ],
                  ),
                ),
              ),
          ],
          if (outbox.isNotEmpty) ...[
            const SizedBox(height: 24),
            Text('Versandstand', style: Theme.of(context).textTheme.titleLarge),
            for (final item in outbox)
              Card(
                child: ListTile(
                  title: Text('${item['recipient'] ?? ''}'),
                  subtitle: Text(
                    const {
                          'pending': 'Freigegeben, Zustellung ausstehend',
                          'sending': 'Zustellung läuft',
                          'sent': 'Vom Mailserver angenommen · Empfang nicht bestätigt',
                          'failed': 'Zustellung fehlgeschlagen',
                          'unknown': 'Zustellung unklar – bitte abgleichen',
                          'not_sent': 'Nicht versendet',
                        }[item['status']] ??
                        'Zustellung nicht bestätigt',
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }
}

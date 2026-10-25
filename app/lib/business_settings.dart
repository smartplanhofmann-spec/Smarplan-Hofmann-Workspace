import 'package:flutter/material.dart';

import 'business_session.dart';
import 'business_widgets.dart';
import 'business_operations.dart';
import 'business_workflows.dart';
import 'business_adapters.dart';
import 'business_templates.dart';
import 'design.dart';

class BusinessSettingsPage extends StatefulWidget {
  const BusinessSettingsPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessSettingsPage> createState() => _BusinessSettingsPageState();
}

class _BusinessSettingsPageState extends State<BusinessSettingsPage> {
  Map<String, dynamic>? settings;
  String? error;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!widget.session.canWrite('settings.manage')) settings = null;
      setState(() {});
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    try {
      final result = businessMap(
        await widget.session.read('/commercial/settings'),
      );
      if (mounted && widget.session.canWrite('settings.manage'))
        setState(() => settings = result);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> edit() async {
    final initial = settings;
    if (initial == null) return;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Firma und Belegausgabe',
        initial: initial,
        fields: const [
          BusinessField('company_name', 'Firmenname', required: true),
          BusinessField(
            'address_line',
            'Straße und Hausnummer',
            required: true,
          ),
          BusinessField('postal_code', 'Postleitzahl', required: true),
          BusinessField('city', 'Ort', required: true),
          BusinessField(
            'country',
            'Ländercode',
            required: true,
            initial: 'DE',
            hint: 'DE',
          ),
          BusinessField('vat_id', 'Umsatzsteuer-ID'),
          BusinessField('tax_number', 'Steuernummer'),
          BusinessField('email', 'E-Mail'),
          BusinessField('phone', 'Telefon'),
          BusinessField('iban', 'IBAN'),
          BusinessField('bic', 'BIC'),
          BusinessField('website', 'Website'),
          BusinessField('footer', 'Fußzeile', type: BusinessInput.multiline),
          BusinessField(
            'payment_terms',
            'Zahlungshinweis',
            type: BusinessInput.multiline,
          ),
          BusinessField(
            'default_due_days',
            'Zahlungsziel in Tagen',
            type: BusinessInput.integer,
            required: true,
            initial: 14,
          ),
          BusinessField(
            'issuer_mode',
            'Führendes Rechnungssystem',
            type: BusinessInput.choice,
            required: true,
            choices: {
              'sevdesk': 'Sevdesk führt',
              'own': 'Smartplan stellt eigene Belege aus',
            },
          ),
          BusinessField(
            'issuing_enabled',
            'Eigene Festschreibung freischalten',
            type: BusinessInput.toggle,
          ),
          BusinessField(
            'cutover_ack',
            'Betrieblichen Umstieg und Nummernkreise ausdrücklich geprüft',
            type: BusinessInput.toggle,
          ),
          BusinessField(
            'cutover_date',
            'Umstiegsdatum',
            type: BusinessInput.date,
          ),
          BusinessField(
            'einvoice_format',
            'Elektronisches Rechnungsformat',
            type: BusinessInput.choice,
            required: true,
            choices: {
              'none': 'Noch kein elektronischer Ausgabeweg',
              'xrechnung': 'XRechnung (mit offizieller Prüfung)',
              'zugferd': 'ZUGFeRD EN16931 (validiertes XML/PDF-A)',
            },
          ),
        ],
        onSave: (values) async {
          if (values['issuer_mode'] == 'own' &&
              values['issuing_enabled'] == true) {
            if (values['cutover_ack'] != true || values['cutover_date'] == null)
              throw const FormatException(
                'Bitte erst den geprüften Umstieg mit Datum bestätigen.',
              );
            if (!await businessConfirm(
              context,
              title: 'Eigene Belegausgabe freischalten?',
              message: 'Eine Rechnung darf nur in einem System ausgestellt werden. Bestätigen Sie den betrieblich geprüften Umstieg, die Ausstellerdaten, Nummernkreise und Aufbewahrung. Bestehende Sevdesk-Belege bleiben unverändert.',
              action: 'Geprüften Umstieg speichern',
            ))
              throw const FormatException('Der Umstieg wurde nicht bestätigt.');
          }
          await widget.session.command(
            'commercial-settings-${initial['revision']}',
            '/commercial/settings',
            {'revision': initial['revision'], ...values},
          );
        },
      ),
    );
    if (mounted) await load();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.canWrite('settings.manage'))
      return const BusinessEmpty(
        'Kein Zugriff',
        'Diese Einstellungen benötigen Administrationsrechte.',
      );
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text(
          'Einstellungen',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: 20),
        if (error != null) Notice(error!, error: true),
        if (settings != null)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${settings!['company_name'] ?? 'Betriebsdaten'}',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    settings!['issuer_mode'] == 'own' &&
                            settings!['issuing_enabled'] == true
                        ? 'Eigene Belegausgabe freigeschaltet'
                        : 'Sevdesk führt · eigene Belegausgabe gesperrt',
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Ein Umstieg wird gesondert geprüft. Ein Hash oder eine gezeichnete Unterschrift ersetzt keine betriebliche Verfahrensdokumentation.',
                  ),
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: edit,
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text('Firma und Ausgabe bearbeiten'),
                  ),
                ],
              ),
            ),
          ),
        const SizedBox(height: 16),
        if (widget.session.hasModule('documents') &&
            widget.session.can('finance.read'))
          Card(
            child: ListTile(
              leading: const Icon(Icons.auto_awesome_motion_outlined),
              title: const Text('Vorlagen und Textbausteine'),
              subtitle: const Text(
                'Eigene Angebote, Rechnungen und wiederverwendbare Texte.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      BusinessTemplatesPage(session: widget.session),
                ),
              ),
            ),
          ),
        if (widget.session.hasModule('adapters'))
          Card(
            child: ListTile(
              leading: const Icon(Icons.sync_alt_outlined),
              title: const Text('Schnittstellenprofile'),
              subtitle: const Text(
                'Dateiimporte und geprüfte Übergaben; Anbieterzugänge getrennt freigeben.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) => BusinessAdaptersPage(session: widget.session),
                ),
              ),
            ),
          ),
        if (widget.session.hasModule('finance'))
          Card(
            child: ListTile(
              leading: const Icon(Icons.rule_outlined),
              title: const Text('Mahnregeln'),
              subtitle: const Text(
                'Stufen und Vorlagen. Versand weiterhin nur nach Freigabe.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      BusinessDunningSettingsPage(session: widget.session),
                ),
              ),
            ),
          ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.view_kanban_outlined),
            title: const Text('Projektstatus verwalten'),
            subtitle: const Text(
              'Eigene Status ohne vorgeschriebene Reihenfolge.',
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.push<void>(
              context,
              MaterialPageRoute(
                builder: (_) => Scaffold(
                  appBar: AppBar(title: const Text('Projektstatus')),
                  body: BusinessAreaPage(
                    session: widget.session,
                    area: 'settings',
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class BusinessCostPage extends StatefulWidget {
  const BusinessCostPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessCostPage> createState() => _BusinessCostPageState();
}

class _BusinessCostPageState extends State<BusinessCostPage> {
  Map<String, dynamic>? data;
  String? error;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!widget.session.can('finance.read')) data = null;
      setState(() {});
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    try {
      final result = businessMap(
        await widget.session.read(
          '/projects/${widget.session.projectId}/costs',
        ),
      );
      if (mounted && widget.session.can('finance.read'))
        setState(() => data = result);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.can('finance.read'))
      return const BusinessEmpty(
        'Kalkulation nicht freigegeben',
        'Kosten benötigen eigene Finanzrechte.',
      );
    final d = data;
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Text('Soll und Ist', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 12),
        const Notice(
          'Istkosten basieren auf gebuchten Materialbewegungen und freigegebenen Zeiten mit dem historischen Kostensatz. Weitere noch nicht gebuchte Kosten sind darin nicht enthalten.',
        ),
        if (error != null) Notice(error!, error: true),
        if (d == null && error == null) const LinearProgressIndicator(),
        if (d != null) ...[
          if (d['costs_complete'] == false)
            Notice(
              'Die Istkosten sind unvollständig: Für ${d['missing_rates_count'] ?? 'einige'} Zeitnachweise fehlen historische Kostensätze. Ein verbleibendes Budget wird deshalb nicht berechnet.',
              error: true,
            ),
          for (final field in const {
            'budget_net': 'Geplantes Budget',
            'approved_changes_net': 'Freigegebene Nachträge',
            'material_actual_net': 'Gebuchtes Material',
            'labor_actual_net': 'Freigegebene Lohnkosten',
            'actual_net': 'Erfasste Istkosten',
            'remaining_net': 'Verbleibender Betrag',
          }.entries)
            Card(
              child: ListTile(
                title: Text(field.value),
                trailing: Text(
                  businessMoney(d[field.key]),
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            ),
          const SizedBox(height: 16),
          Text('Zeitnachweise', style: Theme.of(context).textTheme.titleLarge),
          for (final item in (d['approved_times'] as List? ?? []).map(
            businessMap,
          ))
            ListTile(
              title: Text(businessDate(item['work_date'])),
              subtitle: Text(
                '${item['net_seconds']} Sekunden · historischer Kostennachweis',
              ),
            ),
          Text(
            'Materialnachweise',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          for (final item in (d['material_movements'] as List? ?? []).map(
            businessMap,
          ))
            ListTile(
              title: Text('${item['article_snapshot']?['name'] ?? 'Material'}'),
              subtitle: Text(
                '${item['quantity']} · ${businessMoney(item['cost_net'])}',
              ),
            ),
        ],
      ],
    );
  }
}

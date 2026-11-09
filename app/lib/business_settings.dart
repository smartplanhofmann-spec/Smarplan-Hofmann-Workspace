import 'package:flutter/material.dart';

import 'business_session.dart';
import 'business_custom_fields.dart';
import 'business_company_handover.dart';
import 'business_privacy_cases.dart';
import 'business_migrations.dart';
import 'business_widgets.dart';
import 'business_operations.dart';
import 'business_workflows.dart';
import 'business_adapters.dart';
import 'business_templates.dart';
import 'business_organization.dart';
import 'business_permissions.dart';
import 'design.dart';

({String message, bool unsupported}) commercialCountryScopeView(
  Map<String, dynamic> scope,
  Map<String, dynamic> settings,
) {
  Never bad() => throw const FormatException(
    'Länderumfang und Firmenangaben sind unvollständig oder geändert. Bitte neu laden.',
  );
  bool valid(dynamic value) =>
      value is Map &&
      value['schema_version'] is int &&
      value['schema_version'] == 1 &&
      value['domain'] == 'commercial_invoice' &&
      value['country'] == 'DE' &&
      value['currency'] == 'EUR' &&
      value['currency_scale'] is int &&
      value['currency_scale'] == 2 &&
      value['contract'] == 'de_commercial_invoice_eur_v1' &&
      value['package_hash'] is String &&
      RegExp(r'^[a-f0-9]{64}$').hasMatch(value['package_hash']);
  if (scope['schema_version'] is! int ||
      scope['schema_version'] != 1 ||
      scope['domain'] != 'commercial_invoice' ||
      scope['currency'] != 'EUR' ||
      scope['settings_revision'] is! int ||
      scope['settings_revision'] != settings['revision'] ||
      scope['issuer_country'] is! String ||
      scope['issuer_country'] != settings['country'] ||
      scope['supported_issuer'] is! bool ||
      scope['scope_note'] is! String ||
      (scope['scope_note'] as String).trim().isEmpty ||
      (scope['scope_note'] as String).length > 1000 ||
      scope['supported'] is! List ||
      (scope['supported'] as List).length != 1)
    bad();
  if (!valid(scope['supported'][0]) ||
      scope['supported_issuer'] != (scope['issuer_country'] == 'DE') ||
      (scope['supported_issuer'] == true
          ? !valid(scope['selected'])
          : scope['selected'] != null))
    bad();
  return (
    message:
        '${scope['supported_issuer'] == true ? '' : 'Dieses Ausstellerland wird für neue eigene Rechnungen derzeit nicht unterstützt. '}Ausstellerland: ${scope['issuer_country'] == '' ? 'nicht angegeben' : scope['issuer_country']}. ${scope['scope_note']}',
    unsupported: scope['supported_issuer'] != true,
  );
}

class BusinessSettingsPage extends StatefulWidget {
  const BusinessSettingsPage({
    super.key,
    required this.session,
    this.onOpenSection,
    this.onProject,
  });
  final BusinessSession session;
  final ValueChanged<String>? onOpenSection;
  final void Function(Map<String, dynamic>)? onProject;
  @override
  State<BusinessSettingsPage> createState() => _BusinessSettingsPageState();
}

class _BusinessSettingsPageState extends State<BusinessSettingsPage> {
  Map<String, dynamic>? settings;
  ({String message, bool unsupported})? countryScope;
  String? error;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!widget.session.can('settings.manage')) {
        settings = null;
        countryScope = null;
      }
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
      final scope = widget.session.hasFeature('commercial_country_scope')
          ? commercialCountryScopeView(
              businessMap(await widget.session.read('/commercial/rule-scope')),
              result,
            )
          : null;
      if (mounted && widget.session.can('settings.manage'))
        setState(() {
          settings = result;
          countryScope = scope;
        });
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
    if (!widget.session.can('settings.manage'))
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
        if (widget.session.hasFeature('organization_modules')) ...[
          BusinessOrganizationPanel(
            session: widget.session,
            onOpenSection: widget.onOpenSection,
          ),
          const SizedBox(height: 20),
        ],
        if (error != null) Notice(error!, error: true),
        if (countryScope != null)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Länderumfang der Rechnungsstellung',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  Notice(
                    countryScope!.message,
                    error: countryScope!.unsupported,
                  ),
                ],
              ),
            ),
          ),
        if (widget.session.hasFeature('custom_fields'))
          Card(
            child: ListTile(
              leading: const Icon(Icons.playlist_add),
              title: const Text('Zusatzfelder verwalten'),
              subtitle: const Text(
                'Eigene Angaben für Kontakte, Projekte und Geräte.',
              ),
              onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      BusinessCustomFieldsPage(session: widget.session),
                ),
              ),
            ),
          ),
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
                    onPressed: widget.session.canWrite('settings.manage')
                        ? edit
                        : null,
                    icon: const Icon(Icons.edit_outlined),
                    label: const Text('Firma und Ausgabe bearbeiten'),
                  ),
                ],
              ),
            ),
          ),
        const SizedBox(height: 16),
        if (widget.session.can('privacy.manage') &&
            widget.session.hasFeature('privacy_cases'))
          Card(
            child: ListTile(
              leading: const Icon(Icons.privacy_tip_outlined),
              title: const Text('Datenschutzfälle'),
              subtitle: const Text(
                'Betroffenenanfragen, Fristen, Quellenprüfung und geschützte Auskunft.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      BusinessPrivacyCasesPage(session: widget.session),
                ),
              ),
            ),
          ),
        if (widget.session.hasFeature('company_handover') &&
            widget.session.hasModule('company_handover'))
          Card(
            child: ListTile(
              leading: const Icon(Icons.inventory_2_outlined),
              title: const Text('Unternehmensübergabe'),
              subtitle: const Text(
                'Nur Geschäftsführung: Unternehmensarchiv, Zugänge und dokumentierte Ausstiegsprüfung.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      BusinessCompanyHandoverPage(session: widget.session),
                ),
              ),
            ),
          ),
        if (widget.session.hasModule('foundation'))
          Card(
            child: ListTile(
              leading: const Icon(Icons.admin_panel_settings_outlined),
              title: const Text('Fachrechte verwalten'),
              subtitle: const Text(
                'Benutzerrechte global oder für einzelne Projekte prüfen.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      BusinessPermissionsPage(session: widget.session),
                ),
              ),
            ),
          ),
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
        if (widget.session.hasFeature('file_migrations') &&
            widget.session.hasModule('migrations') &&
            [
              'settings.manage',
              'contacts.read',
              'finance.read',
              'documents.read',
            ].every(widget.session.can))
          Card(
            child: ListTile(
              leading: const Icon(Icons.drive_folder_upload_outlined),
              title: const Text('Kontrollierter Dateiimport'),
              subtitle: const Text(
                'Originale, Feldzuordnung, Dubletten, Vorschau und Abgleich.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) => BusinessMigrationsPage(
                    session: widget.session,
                    onProject: widget.onProject,
                  ),
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

import 'dart:async';

import 'package:flutter/material.dart';

import 'business_documents.dart';
import 'business_assistant.dart';
import 'business_service.dart';
import 'business_communication_history.dart';
import 'business_company_overview.dart';
import 'business_accounting_euer.dart';
import 'business_finance.dart';
import 'business_settings.dart';
import 'business_project_economics.dart';
import 'business_project_milestones.dart';
import 'business_customer_workspace.dart';
import 'business_media.dart';
import 'business_document_access.dart';
import 'business_contacts.dart';
import 'business_operations.dart';
import 'business_planning.dart';
import 'business_session.dart';
import 'business_custom_fields.dart';
import 'business_time.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'offline_plans.dart';
import 'legacy_offline_recovery.dart';
import 'legacy_offline_recovery_page.dart';

typedef _Destination = ({
  String id,
  String label,
  IconData icon,
  String? module,
  String? permission,
});
const _destinations = <_Destination>[
  (
    id: 'overview',
    label: 'Übersicht',
    icon: Icons.space_dashboard_outlined,
    module: 'foundation',
    permission: null,
  ),
  (
    id: 'projects',
    label: 'Projekte',
    icon: Icons.folder_open_outlined,
    module: 'foundation',
    permission: null,
  ),
  (
    id: 'contacts',
    label: 'Kontakte',
    icon: Icons.contacts_outlined,
    module: 'foundation',
    permission: 'contacts.read',
  ),
  (
    id: 'planning',
    label: 'Einsatzplanung',
    icon: Icons.calendar_view_week_outlined,
    module: 'planning',
    permission: 'planning.read',
  ),
  (
    id: 'documents',
    label: 'Belege',
    icon: Icons.description_outlined,
    module: 'documents',
    permission: 'finance.read',
  ),
  (
    id: 'finance',
    label: 'Finanzen',
    icon: Icons.account_balance_outlined,
    module: 'finance',
    permission: 'finance.read',
  ),
  (
    id: 'material',
    label: 'Material',
    icon: Icons.inventory_2_outlined,
    module: 'inventory',
    permission: 'inventory.read',
  ),
  (
    id: 'personnel',
    label: 'Personal',
    icon: Icons.badge_outlined,
    module: 'planning',
    permission: 'time.own',
  ),
  (
    id: 'service',
    label: 'Kundenservice',
    icon: Icons.support_agent_outlined,
    module: 'service',
    permission: 'contacts.read',
  ),
  (
    id: 'assistant',
    label: 'Assistent',
    icon: Icons.auto_awesome_outlined,
    module: 'assistant',
    permission: 'assistant.use',
  ),
  (
    id: 'settings',
    label: 'Einstellungen',
    icon: Icons.settings_outlined,
    module: 'foundation',
    permission: 'settings.manage',
  ),
];

class BusinessHome extends StatefulWidget {
  const BusinessHome({
    super.key,
    required this.session,
    required this.onProject,
    required this.onLegacy,
    required this.onLogout,
    this.onInquiries,
    this.onIntegrations,
    this.repository,
  });
  final BusinessSession session;
  final void Function(Map<String, dynamic>) onProject;
  final VoidCallback onLegacy, onLogout;
  final VoidCallback? onInquiries, onIntegrations;
  final OfflinePlans? repository;
  @override
  State<BusinessHome> createState() => _BusinessHomeState();
}

class _BusinessHomeState extends State<BusinessHome>
    with WidgetsBindingObserver {
  String selected = 'overview';
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    WidgetsBinding.instance.addObserver(this);
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(widget.session.load());
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  List<_Destination> get availableDestinations => _destinations
      .where(
        (d) =>
            widget.session.hasModule(d.module!) &&
            (d.id != 'service' || widget.session.hasFeature('service_cases')) &&
            (d.id != 'assistant' ||
                widget.session.hasFeature('assistant_workflow')) &&
            (d.permission == null || widget.session.can(d.permission!)),
      )
      .toList();
  List<_Destination> get destinations => availableDestinations
      .where((d) => widget.session.sectionVisible(d.id))
      .toList();
  List<_Destination> get hiddenDestinations => availableDestinations
      .where((d) => !widget.session.sectionVisible(d.id))
      .toList();
  Widget navigation(bool drawer) => SafeArea(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(12, 12, 12, 24),
            child: Row(
              children: [
                PlanMark(size: 32),
                SizedBox(width: 12),
                Flexible(
                  child: Text(
                    'smartplan',
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 21, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              children: [
                for (final d in destinations)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: ListTile(
                      selected: selected == d.id,
                      selectedTileColor: OfficeColors.blueTint,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      leading: Icon(d.icon),
                      title: Text(d.label),
                      onTap: () {
                        setState(() => selected = d.id);
                        if (drawer) Navigator.pop(context);
                      },
                    ),
                  ),
                if (hiddenDestinations.isNotEmpty)
                  ExpansionTile(
                    key: const ValueKey('organization-hidden-sections'),
                    leading: const Icon(Icons.unfold_more_outlined),
                    title: const Text('Weitere Bereiche'),
                    children: [
                      for (final d in hiddenDestinations)
                        ListTile(
                          selected: selected == d.id,
                          leading: Icon(d.icon),
                          title: Text(d.label),
                          onTap: () {
                            setState(() => selected = d.id);
                            if (drawer) Navigator.pop(context);
                          },
                        ),
                    ],
                  ),
                if (widget.onInquiries != null)
                  ListTile(
                    leading: const Icon(Icons.inbox_outlined),
                    title: const Text('Anfragen'),
                    onTap: () {
                      if (drawer) Navigator.pop(context);
                      widget.onInquiries!();
                    },
                  ),
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 14),
                  child: Divider(),
                ),
                if (widget.onIntegrations != null)
                  ListTile(
                    leading: const Icon(Icons.hub_outlined),
                    title: const Text('Integrationen'),
                    onTap: () {
                      if (drawer) Navigator.pop(context);
                      widget.onIntegrations!();
                    },
                  ),
                if (widget.repository != null && widget.session.allowed)
                  ListTile(
                    leading: const Icon(Icons.fact_check_outlined),
                    title: const Text('Alte Offline-Aufträge prüfen'),
                    onTap: () {
                      if (drawer) Navigator.pop(context);
                      final session = widget.session,
                          generation = widget.session.generation;
                      final recovery = LegacyOfflineRecovery(
                        api: session.api,
                        device: widget.repository!.device,
                        accessChanges: session,
                        allowed: () =>
                            session.allowed && session.generation == generation,
                      );
                      Navigator.of(context).push<void>(
                        MaterialPageRoute(
                          builder: (_) =>
                              LegacyOfflineRecoveryPage(recovery: recovery),
                        ),
                      );
                    },
                  ),
                ListTile(
                  leading: const Icon(Icons.more_horiz),
                  title: const Text('Weitere Verwaltung'),
                  onTap: () {
                    if (drawer) Navigator.pop(context);
                    widget.onLegacy();
                  },
                ),
              ],
            ),
          ),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Abmelden'),
            onTap: widget.onLogout,
          ),
        ],
      ),
    ),
  );
  Widget content() {
    final session = widget.session;
    return switch (selected) {
      'overview' || 'projects' => BusinessOverview(
        session: session,
        onProject: widget.onProject,
        projectsOnly: selected == 'projects',
      ),
      'material' || 'personnel' => BusinessAreaPage(
        key: ValueKey(selected),
        session: session,
        area: selected,
      ),
      'service' => BusinessServicePage(
        session: session,
        onProject: widget.onProject,
      ),
      'assistant' => BusinessAssistantPage(session: session),
      'contacts' => BusinessContactsPage(
        session: session,
        onProject: widget.onProject,
      ),
      'planning' => BusinessPlanningPage(session: session),
      'documents' => BusinessDocumentsPage(session: session),
      'finance' => BusinessFinancePage(session: session),
      'settings' => BusinessSettingsPage(
        session: session,
        onProject: widget.onProject,
        onOpenSection: (section) {
          final destination = _destinations
              .where((d) => d.id == section)
              .firstOrNull;
          if (destination != null &&
              session.hasModule(destination.module!) &&
              (destination.permission == null ||
                  session.can(destination.permission!))) {
            setState(() => selected = section);
          }
        },
      ),
      _ => BusinessOverview(session: session, onProject: widget.onProject),
    };
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.allowed)
      return const Scaffold(
        body: Center(
          child: Text(
            'Der Zugang ist nicht mehr verfügbar. Bitte melden Sie sich erneut an.',
          ),
        ),
      );
    return LayoutBuilder(
      builder: (context, box) {
        final wide = box.maxWidth >= 1000;
        return Scaffold(
          appBar: wide
              ? null
              : AppBar(
                  title: Text(
                    availableDestinations
                            .where((d) => d.id == selected)
                            .firstOrNull
                            ?.label ??
                        'Smartplan',
                  ),
                ),
          drawer: wide ? null : Drawer(child: navigation(true)),
          body: Row(
            children: [
              if (wide)
                Container(
                  width: 248,
                  decoration: const BoxDecoration(
                    color: OfficeColors.sidebar,
                    border: Border(right: BorderSide(color: OfficeColors.line)),
                  ),
                  child: Material(
                    color: OfficeColors.sidebar,
                    child: navigation(false),
                  ),
                ),
              Expanded(
                child: SafeArea(
                  child: Column(
                    children: [
                      if (widget.session.readonly)
                        const Padding(
                          padding: EdgeInsets.all(16),
                          child: Notice(
                            'Lesemodus: Gespeicherte Daten und Archive bleiben verfügbar. Änderungen und Versand sind pausiert.',
                          ),
                        ),
                      if (!widget.session.readonly &&
                          !widget.session.sectionEnabled(selected))
                        const Padding(
                          padding: EdgeInsets.all(16),
                          child: Notice(
                            'Dieser Bereich ist fachlich deaktiviert. Gespeicherte Vorgänge und Exporte bleiben entsprechend Ihren Rechten erreichbar. Neue Änderungen sind gesperrt.',
                          ),
                        ),
                      Expanded(child: content()),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class BusinessOverview extends StatefulWidget {
  const BusinessOverview({
    super.key,
    required this.session,
    required this.onProject,
    this.projectsOnly = false,
  });
  final BusinessSession session;
  final void Function(Map<String, dynamic>) onProject;
  final bool projectsOnly;
  @override
  State<BusinessOverview> createState() => _BusinessOverviewState();
}

class _BusinessOverviewState extends State<BusinessOverview> {
  Map<String, dynamic>? overview;
  Map<String, dynamic>? metrics;
  List<Map<String, dynamic>> feed = [];
  String? error;
  bool loading = true;
  String filter = '';
  String? status;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (!mounted) return;
    metrics = null;
    if (!widget.session.allowed) {
      overview = null;
      metrics = null;
      feed = [];
    }
    setState(() {});
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
      metrics = null;
    });
    try {
      final data = businessMap(await widget.session.read('/overview'));
      if (!mounted || !widget.session.allowed) return;
      setState(() => overview = data);
      if (!widget.projectsOnly) {
        if (widget.session.hasFeature('company_overview')) {
          final result = companyOverviewData(
            await widget.session.read(
              widget.session.query('/overview/metrics'),
            ),
          );
          if (!mounted || !widget.session.allowed) return;
          setState(() => metrics = result);
        }
        final messages = businessItems(await widget.session.read('/feed'));
        if (mounted && widget.session.allowed) setState(() => feed = messages);
      }
    } catch (e) {
      if (mounted && widget.session.allowed) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.allowed) return const SizedBox();
    final projects = (overview?['projects'] as List? ?? [])
        .map(businessMap)
        .where(
          (p) =>
              (status == null || p['status_id'] == status) &&
              '${p['name']} ${p['customer']} ${p['project_number'] ?? ''}'
                  .toLowerCase()
                  .contains(filter.toLowerCase()),
        )
        .toList();
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
                widget.projectsOnly ? 'Projekte' : 'Ihr Betrieb im Blick',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              IconButton(
                tooltip: 'Aktualisieren',
                onPressed: loading ? null : load,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Jedes Projekt hat seinen eigenen Ablauf. Aufgaben, Termine und Belege bleiben direkt miteinander verbunden.',
          ),
          const SizedBox(height: 24),
          if (error != null) Notice(error!, error: true),
          if (loading) const LinearProgressIndicator(),
          if (!widget.projectsOnly && metrics != null)
            BusinessCompanyOverview(
              data: metrics!,
              onProject: (id) {
                final matching = (overview?['projects'] as List? ?? [])
                    .map(businessMap)
                    .where((p) => p['id'] == id);
                if (matching.isNotEmpty) widget.onProject(matching.first);
              },
              onAccounting: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => BusinessEuerPage(session: widget.session),
                ),
              ),
            ),
          TextField(
            decoration: const InputDecoration(
              labelText: 'Projekt, Kunde oder Projektnummer suchen',
              prefixIcon: Icon(Icons.search),
            ),
            onChanged: (v) => setState(() => filter = v),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              ChoiceChip(
                label: const Text('Alle Projekte'),
                selected: status == null,
                onSelected: (_) => setState(() => status = null),
              ),
              for (final s in (overview?['statuses'] as List? ?? []).map(
                businessMap,
              ))
                ChoiceChip(
                  label: Text('${s['name']}'),
                  selected: status == s['id'],
                  onSelected: (_) => setState(() => status = s['id']),
                ),
            ],
          ),
          const SizedBox(height: 16),
          if (!loading && projects.isEmpty && error == null)
            const BusinessEmpty(
              'Keine passenden Projekte',
              'Ändern Sie die Suche oder den Statusfilter.',
            ),
          for (final p in projects)
            Card(
              child: ListTile(
                contentPadding: const EdgeInsets.all(20),
                leading: const IconTile(Icons.folder_open_outlined),
                title: Text('${p['name']}'),
                subtitle: Text(
                  '${p['customer'] ?? 'Kein Kunde zugeordnet'}${p['status'] == null ? '' : ' · ${p['status']['name']}'}${p['site_address'] == null || p['site_address'] == '' ? '' : '\n${p['site_address']}'}',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => widget.onProject(p),
              ),
            ),
          if (!widget.projectsOnly) ...[
            const SizedBox(height: 24),
            Text(
              'Aus den Projekten',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            if (!loading && feed.isEmpty && error == null)
              const BusinessEmpty(
                'Noch keine Meldungen',
                'Neue Projektmeldungen erscheinen hier entsprechend Ihren Zugriffsrechten.',
              ),
            for (final item in feed)
              Card(
                child: ListTile(
                  title: Text('${item['summary'] ?? item['text'] ?? ''}'),
                  subtitle: Text(businessDate(item['created_at'], time: true)),
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class BusinessProjectFeature extends StatelessWidget {
  const BusinessProjectFeature({
    super.key,
    required this.session,
    required this.feature,
    this.repository,
    this.visible = true,
  });
  final BusinessSession session;
  final String feature;
  final OfflinePlans? repository;
  final bool visible;
  @override
  Widget build(BuildContext context) => switch (feature) {
    'Kommunikation' => BusinessCommunicationHistoryPage(
      session: session,
      active: visible,
    ),
    'Zusatzfelder' => BusinessCustomFieldsPage(
      session: session,
      entityType: 'project',
      entityId: session.projectId,
    ),
    'Kundenservice' => BusinessServicePage(session: session),
    'Assistent' => BusinessAssistantPage(session: session),
    'Belege' => BusinessDocumentsPage(session: session),
    'Einsatzplanung' => BusinessPlanningPage(session: session),
    'Meilensteine' => BusinessProjectMilestonesPage(
      session: session,
      active: visible,
    ),
    'Arbeitszeit' => BusinessTimePage(session: session, repository: repository),
    'Material' => BusinessAreaPage(session: session, area: 'material'),
    'Dokumentation' => BusinessAreaPage(
      session: session,
      area: 'documentation',
      repository: repository,
    ),
    'Wartung' => BusinessAreaPage(session: session, area: 'maintenance'),
    'Kalkulation' =>
      projectEconomicsReadable(session)
          ? BusinessProjectEconomicsPage(session: session)
          : BusinessCostPage(session: session),
    'Fotos' => BusinessMediaPage(session: session, repository: repository),
    'Unterlagenfreigabe' => BusinessDocumentAccessPage(session: session),
    'Kundenportal' => BusinessCustomerWorkspacePage(session: session),
    'Finanzen' => BusinessFinancePage(session: session),
    _ => const SizedBox(),
  };
}

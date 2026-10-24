import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'admin_pages.dart';
import 'api.dart';
import 'project_page.dart';
import 'design.dart';
import 'home_views.dart';
import 'customer_pages.dart';
import 'mfa_dialog.dart';
import 'offline_plans.dart';
import 'plan_pages.dart';
import 'inquiry_pages.dart';
import 'app_version.dart';
import 'integration_pages.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  LicenseRegistry.addLicense(() async* {
    yield LicenseEntryWithLineBreaks([
      'Inter',
    ], await rootBundle.loadString('assets/fonts/OFL.txt'));
  });
  runApp(const OfficeApp());
}

class OfficeApp extends StatelessWidget {
  final OfficeApi? api;
  const OfficeApp({super.key, this.api});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Smartplan Office',
    debugShowCheckedModeBanner: false,
    theme: officeTheme(),
    home: OfficeHome(api: api),
  );
}

class OfficeHome extends StatefulWidget {
  final OfficeApi? api;
  const OfficeHome({super.key, this.api});
  @override
  State<OfficeHome> createState() => _OfficeHomeState();
}

class _OfficeHomeState extends State<OfficeHome> with WidgetsBindingObserver {
  late final OfficeApi api;
  OfflinePlans? offline;
  bool offlineMode = false;
  final email = TextEditingController(), password = TextEditingController();
  final loginForm = GlobalKey<FormState>();
  Map<String, dynamic>? user, storage;
  List<dynamic> projects = [];
  bool busy = false;
  String? error;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    api = widget.api ?? OfficeApi();
    api.addListener(sessionChanged);
    if (widget.api == null) {
      offline = OfflinePlans(api: api)..addListener(offlineChanged);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    offline?.removeListener(offlineChanged);
    offline?.dispose();
    api.removeListener(sessionChanged);
    if (widget.api == null) api.dispose();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && offline?.active == true)
      unawaited(offline!.sync());
  }

  void offlineChanged() {
    if (mounted) setState(() {});
  }

  Future<void> resumeOffline() => run(() async {
    await offline!.resume();
    if (mounted)
      setState(() {
        user = offline!.user;
        projects = offline!.projects;
        offlineMode = true;
      });
  });
  Future<void> openOfflinePlans(Map<String, dynamic> project) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => offline!.workspaceSupported
            ? ProjectPage(
                api: api,
                project: project,
                role: user!['role'],
                repository: offline,
                offlineMode: true,
              )
            : PlansPage(
                api: api,
                project: project,
                canWrite: [
                  'owner',
                  'manager',
                  'technician',
                ].contains(user!['role']),
                repository: offline,
              ),
      ),
    );
  }

  void sessionChanged() {
    if (api.token != null || !mounted) return;
    Navigator.of(context).popUntil((route) => route.isFirst);
    setState(() {
      user = null;
      projects = [];
      storage = null;
      offlineMode = false;
      error = 'Sitzung beendet. Bitte erneut anmelden.';
    });
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> loadProjects() async {
    final session = api.token;
    final account = user?['id'];
    final items = List<dynamic>.from(await api.call('/api/projects'));
    if (api.token != session || user?['id'] != account) return;
    Map<String, dynamic>? state;
    if (user?['role'] == 'owner')
      state = Map<String, dynamic>.from(await api.call('/api/storage/status'));
    if (api.token != session || user?['id'] != account) return;
    if (offline?.active == true) await offline!.refreshProjects(items);
    if (api.token != session || user?['id'] != account) return;
    if (mounted)
      setState(() {
        projects = items;
        storage = state;
      });
  }

  Future<void> login() async {
    if (!loginForm.currentState!.validate()) return;
    await run(() async {
      await offline?.leave();
      var result = await api.call('/api/login', {
        'email': email.text.trim(),
        'password': password.text,
      });
      password.clear();
      if (result['mfa_required'] == true) {
        final pending = Map<String, dynamic>.from(result);
        if (!mounted) return;
        result = await showDialog<Map<String, dynamic>>(
          context: context,
          barrierDismissible: false,
          builder: (_) => MfaDialog(
            api: api,
            challenge: pending['challenge'] as String,
            enrollment: pending['enrollment'] as Map<String, dynamic>?,
          ),
        );
        if (result == null || !mounted) return;
        final codes = result['recovery_codes'];
        if (codes is List) {
          await showDialog<void>(
            context: context,
            barrierDismissible: false,
            builder: (_) => RecoveryCodesDialog(codes: codes.cast<String>()),
          );
          if (!mounted) return;
        }
      }
      api.token = result['token'];
      try {
        final me = Map<String, dynamic>.from(await api.call('/api/me'));
        if (!mounted) return;
        setState(() => user = me);
        await loadProjects();
        offlineMode = false;
        if (offline != null) {
          try {
            await offline!.login(me, projects);
          } catch (e) {
            if (mounted)
              setState(
                () => error =
                    'Online angemeldet; Offline-Speicher nicht verfügbar: $e',
              );
          }
        }
      } catch (_) {
        api.token = null;
        if (mounted)
          setState(() {
            user = null;
            projects = [];
            storage = null;
          });
        rethrow;
      } finally {
        password.clear();
      }
    });
  }

  Future<void> logout() => run(() async {
    if ((offline?.pending ?? 0) > 0) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Noch nicht übertragene Pläne'),
          content: const Text(
            'Lokale Änderungen bleiben auf diesem Gerät gespeichert. Abmelden?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Zurück'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Abmelden'),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
    }
    try {
      if (api.token != null) await api.call('/api/logout', {});
    } finally {
      api.token = null;
      await offline?.logout();
      if (mounted)
        setState(() {
          offlineMode = false;
          user = null;
          projects = [];
          storage = null;
        });
    }
  });
  Future<void> newProject({String? customerId}) async {
    if (busy) return;
    List<Map<String, dynamic>> choices = [];
    await run(() async {
      final result = await api.call('/api/customers');
      choices = [
        for (final c in result)
          if (c['active'] == 1) Map<String, dynamic>.from(c),
      ];
    });
    if (!mounted || user == null || error != null) return;
    final values = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => ProjectDialog(customers: choices, customerId: customerId),
    );
    if (!mounted || values == null) return;
    await run(() async {
      await api.call('/api/projects', values);
      await loadProjects();
    });
  }

  Future<void> connectDrive() => run(() async {
    final result = await api.call('/api/storage/connect', {});
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Microsoft-Anmeldung'),
        content: SingleChildScrollView(
          child: SelectableText(
            'Öffnen Sie diese Adresse im Browser und melden Sie sich mit Ihrem OneDrive-Konto an. Aktualisieren Sie anschließend den Verbindungsstatus.\n\n${result['url']}',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Schließen'),
          ),
        ],
      ),
    );
    await loadProjects();
  });

  Future<void> selectStorage(String provider) => run(() async {
    final result = await api.call('/api/storage/provider', {
      'provider': provider,
    });
    if (mounted) setState(() => storage = Map<String, dynamic>.from(result));
  });
  @override
  Widget build(BuildContext context) {
    if (user == null) {
      return LoginView(
        email: email,
        password: password,
        formKey: loginForm,
        busy: busy,
        error: error,
        onLogin: login,
        onOffline: offline == null ? null : resumeOffline,
        connectionLabel: api.version == 'v1'
            ? 'Online-Pilot · ${Uri.parse(api.base).host} · Version $smartplanVersion'
            : 'Version $smartplanVersion',
      );
    }
    if (offlineMode) {
      final usable = offline!.permitted;
      return Scaffold(
        appBar: AppBar(
          title: Text(
            offline!.workspaceSupported
                ? 'Offline-Projektmappe'
                : 'Offline-Projektpläne',
          ),
          actions: [
            TextButton(
              onPressed: busy ? null : logout,
              child: const Text('Online anmelden'),
            ),
          ],
        ),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const PageHeading(
              title: 'Auf diesem Gerät',
              subtitle: 'Gespeicherte Projekte und lokale Änderungen.',
            ),
            const SizedBox(height: 24),
            Notice(
              usable
                  ? 'Bis zu sieben Tage offline · ${offline!.pending} Änderungen ausstehend'
                  : 'Offline-Freigabe abgelaufen. Bitte online anmelden. Eingaben bleiben erhalten.',
              error: !usable,
            ),
            const Text(
              'Vorbereitete Projektmappen und Pläne bleiben lokal verfügbar. Anfragen, externe Ablagen und unterschriebene Berichte benötigen Verbindung.',
            ),
            const SizedBox(height: 20),
            if (error != null) Notice(error!),
            if (usable)
              for (final project in offline!.projects)
                Card(
                  clipBehavior: Clip.antiAlias,
                  child: ListTile(
                    title: Text(project['name']),
                    subtitle: Text(project['customer']?.toString() ?? ''),
                    leading: const IconTile(Icons.folder_open_rounded),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    enabled: usable && !busy,
                    onTap: () =>
                        openOfflinePlans(Map<String, dynamic>.from(project)),
                  ),
                ),
          ],
        ),
      );
    }
    return WorkspaceView(
      user: user!,
      projects: projects,
      storage: storage,
      busy: busy,
      error: error,
      onRefresh: () => run(loadProjects),
      onInquiries: user!['role'] == 'owner'
          ? () async {
              await Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) => InquiriesPage(
                    api: api,
                    role: user!['role'],
                    onProject: (project) async {
                      if (!mounted) return;
                      final session = api.token;
                      final account = user!['id'];
                      final fresh = List<dynamic>.from(
                        await api.call('/api/projects'),
                      );
                      if (!mounted ||
                          user?['id'] != account ||
                          api.token != session)
                        return;
                      if (offline?.active == true) {
                        await offline!.refreshProjects(fresh);
                      }
                      if (!mounted ||
                          user?['id'] != account ||
                          api.token != session)
                        return;
                      setState(() => projects = fresh);
                      await Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                          builder: (_) => ProjectPage(
                            api: api,
                            project: project,
                            role: user!['role'],
                            repository: offline?.active == true
                                ? offline
                                : null,
                          ),
                        ),
                      );
                    },
                  ),
                ),
              );
              if (mounted && user != null) await run(loadProjects);
            }
          : null,
      onLogout: logout,
      onIntegrations: user!['role'] == 'owner' && api.version == 'v1'
          ? () => Navigator.push<void>(
              context,
              MaterialPageRoute(
                builder: (_) => IntegrationsPage(api: api, role: user!['role']),
              ),
            )
          : null,
      onNewProject: newProject,
      onCustomers: () async {
        await Navigator.push<void>(
          context,
          MaterialPageRoute(
            builder: (_) => CustomersPage(
              api: api,
              onNewProject: (customer) =>
                  newProject(customerId: customer['id']),
            ),
          ),
        );
        if (mounted && user != null) await run(loadProjects);
      },
      onConnectDrive: connectDrive,
      onSelectStorage: selectStorage,
      onUsers: () => Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => UsersPage(api: api, currentUserId: user!['id']),
        ),
      ),
      onProject: (project) async {
        await Navigator.push<void>(
          context,
          MaterialPageRoute(
            builder: (_) => ProjectPage(
              api: api,
              project: project,
              role: user!['role'],
              repository: offline?.active == true ? offline : null,
            ),
          ),
        );
        if (mounted && user != null) await run(loadProjects);
      },
    );
  }
}

class ProjectDialog extends StatefulWidget {
  final List<Map<String, dynamic>> customers;
  final String? customerId;
  const ProjectDialog({super.key, this.customers = const [], this.customerId});
  @override
  State<ProjectDialog> createState() => _ProjectDialogState();
}

class _ProjectDialogState extends State<ProjectDialog> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController(), customer = TextEditingController();
  late String selectedCustomer;
  @override
  void initState() {
    super.initState();
    selectedCustomer = widget.customers.any((c) => c['id'] == widget.customerId)
        ? widget.customerId!
        : '';
  }

  @override
  void dispose() {
    name.dispose();
    customer.dispose();
    super.dispose();
  }

  String? requiredText(String? v) =>
      (v ?? '').trim().isEmpty ? 'Bitte ausfüllen.' : null;
  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Projekt anlegen'),
    content: SizedBox(
      width: 460,
      child: Form(
        key: form,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: name,
                maxLength: 500,
                validator: requiredText,
                decoration: const InputDecoration(labelText: 'Projektname'),
              ),
              const SizedBox(height: 12),
              if (widget.customers.isNotEmpty) ...[
                DropdownButtonFormField<String>(
                  initialValue: selectedCustomer,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Kunde auswählen',
                  ),
                  items: [
                    const DropdownMenuItem(
                      value: '',
                      child: Text('Neuen Kunden anlegen'),
                    ),
                    for (final c in widget.customers)
                      DropdownMenuItem(
                        value: c['id'] as String,
                        child: Text(
                          customerChoiceLabel(c),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: (v) => setState(() => selectedCustomer = v!),
                ),
                const SizedBox(height: 16),
              ],
              if (selectedCustomer.isEmpty)
                TextFormField(
                  controller: customer,
                  maxLength: 500,
                  validator: requiredText,
                  decoration: const InputDecoration(labelText: 'Kunde'),
                ),
            ],
          ),
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(
        onPressed: () {
          if (form.currentState!.validate())
            Navigator.pop(context, <String, dynamic>{
              'name': name.text.trim(),
              if (selectedCustomer.isEmpty)
                'customer': customer.text.trim()
              else
                'customer_id': selectedCustomer,
            });
        },
        child: const Text('Anlegen'),
      ),
    ],
  );
}

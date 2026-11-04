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
import 'offline_vault.dart' show offlineId;
import 'plan_pages.dart';
import 'inquiry_pages.dart';
import 'app_version.dart';
import 'integration_pages.dart';
import 'business_session.dart';
import 'business_shell.dart';

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

class _ProjectCreationContext {
  _ProjectCreationContext(this.api, this.account)
    : token = api.token,
      server = api.base,
      version = api.version;
  final OfficeApi api;
  final Object? account;
  final String? token;
  final String server, version;
}

class _PendingProjectCreation {
  const _PendingProjectCreation(
    this.context,
    this.body,
    this.customers,
    this.receiptsSupported,
  );
  final bool receiptsSupported;
  final _ProjectCreationContext context;
  final Map<String, dynamic> body;
  final List<Map<String, dynamic>> customers;
}

bool _projectDefinitelyRejected(Object error, {bool retry = false}) =>
    error is ApiException &&
    ((!retry && const [400, 403, 404, 422].contains(error.status)) ||
        error.requestResolution == 'not_accepted');

class _OfficeHomeState extends State<OfficeHome> with WidgetsBindingObserver {
  late final OfficeApi api;
  OfflinePlans? offline;
  BusinessSession? business;
  bool offlineMode = false;
  bool _openingProject = false;
  final _administrationChanges = ValueNotifier<int>(0);
  _ProjectCreationContext? _projectCreationContext;
  _PendingProjectCreation? _pendingProjectCreation;
  DialogRoute<bool>? _projectCreationRoute;

  bool _projectContextCurrent(_ProjectCreationContext captured) =>
      mounted &&
      identical(_projectCreationContext, captured) &&
      identical(api, captured.api) &&
      (widget.api == null || identical(widget.api, captured.api)) &&
      user?['id'] == captured.account &&
      captured.account != null &&
      api.token == captured.token &&
      captured.token != null &&
      api.base == captured.server &&
      api.version == captured.version;

  void _dropChangedProjectContext() {
    final captured = _projectCreationContext;
    if (captured == null || _projectContextCurrent(captured)) return;
    _pendingProjectCreation = null;
    final route = _projectCreationRoute;
    _projectCreationRoute = null;
    _projectCreationContext = null;
    _openingProject = false;
    if (route?.isActive == true) {
      scheduleMicrotask(() {
        if (route?.isActive == true) route!.navigator?.removeRoute(route);
      });
    }
  }

  @override
  void didUpdateWidget(covariant OfficeHome oldWidget) {
    super.didUpdateWidget(oldWidget);
    _dropChangedProjectContext();
  }

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
    _administrationChanges.dispose();
    offline?.removeListener(offlineChanged);
    offline?.dispose();
    business?.dispose();
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
    _dropChangedProjectContext();
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

  Future<void> loadProjects({bool Function()? stillCurrent}) async {
    final session = api.token;
    final account = user?['id'];
    final server = api.base, version = api.version;
    bool current() =>
        mounted &&
        (stillCurrent?.call() ?? true) &&
        api.token == session &&
        user?['id'] == account &&
        api.base == server &&
        api.version == version &&
        (widget.api == null || identical(widget.api, api));
    final items = List<dynamic>.from(await api.call('/api/projects'));
    if (!current()) return;
    Map<String, dynamic>? state;
    if (user?['role'] == 'owner')
      state = Map<String, dynamic>.from(await api.call('/api/storage/status'));
    if (!current()) return;
    if (offline?.active == true) await offline!.refreshProjects(items);
    if (!current()) return;
    if (api.version == 'v1' && user != null) {
      if (business == null || !business!.allowed) {
        business?.dispose();
        business = BusinessSession(api: api);
      }
      business!.projects = items.map(businessMap).toList();
      await business!.load();
      if (!current()) return;
    }
    if (current()) {
      setState(() {
        projects = items;
        storage = state;
      });
      _administrationChanges.value++;
    }
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
            await offline!.login(
              me,
              projects,
              businessTime:
                  business?.readonly == false &&
                  business?.hasModule('time') == true &&
                  business!.can('time.own'),
              fieldMedia:
                  business?.readonly == false &&
                  business?.hasModule('operations') == true &&
                  business!.can('documents.write'),
              offlineReports:
                  business?.readonly == false &&
                  business?.hasModule('operations') == true &&
                  business!.can('documents.read') &&
                  business!.can('documents.write'),
            );
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
    if (!mounted ||
        busy ||
        _openingProject ||
        user == null ||
        api.token == null)
      return;
    _dropChangedProjectContext();
    final captured = _ProjectCreationContext(api, user!['id']);
    _projectCreationContext = captured;
    _openingProject = true;
    setState(() => error = null);
    _administrationChanges.value++;
    try {
      final pending = _pendingProjectCreation;
      bool receiptsSupported() =>
          business?.hasFeature('project_creation_receipts') == true;
      final canReplay =
          receiptsSupported() && (pending?.receiptsSupported ?? true);
      List<Map<String, dynamic>> choices;
      if (pending != null) {
        choices = pending.customers;
      } else {
        final result = await api.call('/api/customers');
        if (!_projectContextCurrent(captured)) return;
        choices = [
          for (final c in result)
            if (c['active'] == 1) Map<String, dynamic>.from(c),
        ];
      }
      if (!_projectContextCurrent(captured)) return;
      final route = DialogRoute<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => ProjectDialog(
          customers: choices,
          customerId: customerId,
          originalCommand: pending?.body,
          supportsReplay: canReplay,
          replayAvailable: () =>
              receiptsSupported() &&
              (_pendingProjectCreation?.receiptsSupported ?? true),
          onResolveUnknown: () {
            if (_projectContextCurrent(captured))
              _pendingProjectCreation = null;
          },
          onSubmit: (body) async {
            if (!_projectContextCurrent(captured)) {
              _dropChangedProjectContext();
              return false;
            }
            final previous = _pendingProjectCreation;
            if (previous != null && previous.receiptsSupported) {
              await business?.load();
              if (!_projectContextCurrent(captured)) {
                _dropChangedProjectContext();
                return false;
              }
              if (business?.error != null) {
                throw const ApiException(
                  0,
                  'Die sichere Wiederholung konnte noch nicht geprüft werden. Bitte erneut versuchen.',
                );
              }
            }
            if (previous != null &&
                (!previous.receiptsSupported ||
                    !receiptsSupported() ||
                    !mapEquals(previous.body, body))) {
              throw const ApiException(
                409,
                'Dieser offene Vorgang kann auf diesem Server nicht sicher wiederholt werden. Bitte zuerst die Projektliste prüfen.',
              );
            }
            final original = Map<String, dynamic>.unmodifiable(body);
            _pendingProjectCreation = _PendingProjectCreation(
              captured,
              original,
              choices,
              receiptsSupported(),
            );
            try {
              final result = await api.call('/api/projects', Map.of(original));
              if (!_projectContextCurrent(captured)) {
                _dropChangedProjectContext();
                return false;
              }
              if (result is! Map ||
                  !RegExp(r'^[a-f0-9]{32}$').hasMatch('${result['id']}')) {
                throw const ApiException(
                  0,
                  'Die Projektanlage wurde noch nicht bestätigt.',
                );
              }
              _pendingProjectCreation = null;
              return true;
            } catch (error) {
              if (!_projectContextCurrent(captured)) {
                _dropChangedProjectContext();
                return false;
              }
              if (_projectDefinitelyRejected(error, retry: previous != null))
                _pendingProjectCreation = null;
              rethrow;
            }
          },
        ),
      );
      _projectCreationRoute = route;
      final created = await Navigator.of(context).push(route);
      if (_projectContextCurrent(captured) &&
          (created == true ||
              (!canReplay && pending != null) ||
              (_pendingProjectCreation != null &&
                  (!_pendingProjectCreation!.receiptsSupported ||
                      !receiptsSupported())))) {
        await loadProjects(
          stillCurrent: () => _projectContextCurrent(captured),
        );
      }
    } catch (failure) {
      if (_projectContextCurrent(captured)) {
        setState(() => error = '$failure');
        _administrationChanges.value++;
      }
    } finally {
      if (identical(_projectCreationContext, captured)) {
        _openingProject = false;
        _projectCreationRoute = null;
        if (_pendingProjectCreation == null) _projectCreationContext = null;
      }
    }
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
    WorkspaceView legacyView([VoidCallback? onBack]) => WorkspaceView(
      onBackToWorkspace: onBack,
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
    final legacy = legacyView();
    if (business?.supported == true && business!.allowed) {
      return BusinessHome(
        session: business!,
        repository: offline,
        onProject: legacy.onProject,
        onInquiries: legacy.onInquiries,
        onIntegrations: legacy.onIntegrations,
        onLogout: logout,
        onLegacy: () {
          if (!mounted || user == null || business?.allowed != true) return;
          final navigator = Navigator.of(context);
          late final MaterialPageRoute<void> administration;
          administration = MaterialPageRoute(
            builder: (_) => ListenableBuilder(
              listenable: _administrationChanges,
              builder: (_, _) => legacyView(() {
                if (administration.isCurrent) navigator.pop();
              }),
            ),
          );
          navigator.push<void>(administration);
        },
      );
    }
    return legacy;
  }
}

class ProjectDialog extends StatefulWidget {
  final List<Map<String, dynamic>> customers;
  final String? customerId;
  final Map<String, dynamic>? originalCommand;
  final Future<bool> Function(Map<String, dynamic>) onSubmit;
  final bool supportsReplay;
  final bool Function()? replayAvailable;
  final VoidCallback onResolveUnknown;
  const ProjectDialog({
    super.key,
    this.customers = const [],
    this.customerId,
    this.originalCommand,
    required this.onSubmit,
    required this.supportsReplay,
    this.replayAvailable,
    required this.onResolveUnknown,
  });
  @override
  State<ProjectDialog> createState() => _ProjectDialogState();
}

class _ProjectDialogState extends State<ProjectDialog> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController(), customer = TextEditingController();
  late String selectedCustomer;
  Map<String, dynamic>? originalCommand;
  bool saving = false, confirmingResolution = false;
  String? error;
  bool get supportsReplay =>
      widget.supportsReplay && (widget.replayAvailable?.call() ?? true);
  @override
  void initState() {
    super.initState();
    originalCommand = widget.originalCommand;
    name.text = originalCommand?['name'] as String? ?? '';
    customer.text = originalCommand?['customer'] as String? ?? '';
    selectedCustomer =
        originalCommand?['customer_id'] as String? ??
        (widget.customers.any((c) => c['id'] == widget.customerId)
            ? widget.customerId!
            : '');
  }

  @override
  void dispose() {
    name.dispose();
    customer.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (!mounted ||
        (originalCommand != null && !supportsReplay) ||
        saving ||
        (originalCommand == null && !form.currentState!.validate()))
      return;
    final retry = originalCommand != null;
    final body =
        originalCommand ??
        Map<String, dynamic>.unmodifiable({
          'request_id': offlineId(),
          'name': name.text.trim(),
          if (selectedCustomer.isEmpty)
            'customer': customer.text.trim()
          else
            'customer_id': selectedCustomer,
        });
    setState(() {
      originalCommand = body;
      saving = true;
      error = null;
    });
    try {
      final accepted = await widget.onSubmit(body);
      if (mounted && accepted) Navigator.pop(context, true);
    } catch (failure) {
      if (mounted)
        setState(() {
          if (_projectDefinitelyRejected(failure, retry: retry))
            originalCommand = null;
          error = '$failure';
        });
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  String? requiredText(String? v) =>
      (v ?? '').trim().isEmpty ? 'Bitte ausfüllen.' : null;
  @override
  Widget build(BuildContext context) => PopScope<bool>(
    canPop: !saving,
    child: AlertDialog(
      title: const Text('Projekt anlegen'),
      content: SizedBox(
        width: 460,
        child: Form(
          key: form,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (originalCommand != null && !saving)
                  Notice(
                    supportsReplay
                        ? 'Die Projektanlage ist noch nicht bestätigt. Erneut versuchen wiederholt genau diesen Vorgang. Ihre Eingaben bleiben bis zur Bestätigung erhalten.'
                        : 'Die Projektanlage ist noch nicht bestätigt. Dieser Server unterstützt noch keine sichere Wiederholung. Bitte zuerst die Projektliste prüfen und den Server aktualisieren.',
                    error: false,
                  ),
                if (confirmingResolution)
                  const Notice(
                    'Schließen Sie diesen Vorgang erst ab, nachdem Sie in der Projektliste geprüft haben, ob das Projekt bereits angelegt wurde. Eine neue Anlage könnte sonst ein Duplikat erzeugen.',
                  ),
                if (error != null) Notice(error!),
                if (saving) const LinearProgressIndicator(),
                TextFormField(
                  controller: name,
                  enabled: originalCommand == null && !saving,
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
                    onChanged: originalCommand != null || saving
                        ? null
                        : (v) => setState(() => selectedCustomer = v!),
                  ),
                  const SizedBox(height: 16),
                ],
                if (selectedCustomer.isEmpty)
                  TextFormField(
                    controller: customer,
                    enabled: originalCommand == null && !saving,
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
          onPressed: saving ? null : () => Navigator.pop(context, false),
          child: Text(
            originalCommand == null
                ? 'Abbrechen'
                : supportsReplay
                ? 'Später fortsetzen'
                : 'Projektliste prüfen',
          ),
        ),
        if (originalCommand != null && !supportsReplay)
          TextButton(
            onPressed: saving
                ? null
                : () {
                    if (!mounted) return;
                    if (!confirmingResolution) {
                      setState(() => confirmingResolution = true);
                      return;
                    }
                    widget.onResolveUnknown();
                    Navigator.pop(context, false);
                  },
            child: Text(
              confirmingResolution
                  ? 'Vorgang als geprüft schließen'
                  : 'Als geprüft abschließen',
            ),
          ),
        FilledButton(
          onPressed: saving || (originalCommand != null && !supportsReplay)
              ? null
              : submit,
          child: Text(originalCommand == null ? 'Anlegen' : 'Erneut versuchen'),
        ),
      ],
    ),
  );
}

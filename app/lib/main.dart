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

class _OfficeHomeState extends State<OfficeHome> {
  late final OfficeApi api;
  final email = TextEditingController(), password = TextEditingController();
  final loginForm = GlobalKey<FormState>();
  Map<String, dynamic>? user, storage;
  List<dynamic> projects = [];
  bool busy = false;
  String? error;
  @override
  void initState() {
    super.initState();
    api = widget.api ?? OfficeApi();
    api.addListener(sessionChanged);
  }

  @override
  void dispose() {
    api.removeListener(sessionChanged);
    if (widget.api == null) api.dispose();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  void sessionChanged() {
    if (api.token != null || !mounted) return;
    Navigator.of(context).popUntil((route) => route.isFirst);
    setState(() {
      user = null;
      projects = [];
      storage = null;
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
    final items = List<dynamic>.from(await api.call('/api/projects'));
    Map<String, dynamic>? state;
    if (user?['role'] == 'owner')
      state = Map<String, dynamic>.from(await api.call('/api/storage/status'));
    if (mounted)
      setState(() {
        projects = items;
        storage = state;
      });
  }

  Future<void> login() async {
    if (!loginForm.currentState!.validate()) return;
    await run(() async {
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
    try {
      await api.call('/api/logout', {});
    } finally {
      api.token = null;
      if (mounted)
        setState(() {
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
        connectionLabel: api.version == 'v1'
            ? 'Online-Pilot · ${Uri.parse(api.base).host}'
            : null,
      );
    }
    return WorkspaceView(
      user: user!,
      projects: projects,
      storage: storage,
      busy: busy,
      error: error,
      onRefresh: () => run(loadProjects),
      onLogout: logout,
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
            builder: (_) =>
                ProjectPage(api: api, project: project, role: user!['role']),
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

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'admin_pages.dart';
import 'api.dart';
import 'project_page.dart';
import 'design.dart';
import 'home_views.dart';

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
      final result = await api.call('/api/login', {
        'email': email.text.trim(),
        'password': password.text,
      });
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
  Future<void> newProject() async {
    final values = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => const ProjectDialog(),
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
      onConnectDrive: connectDrive,
      onUsers: () => Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => UsersPage(api: api, currentUserId: user!['id']),
        ),
      ),
      onProject: (project) => Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) =>
              ProjectPage(api: api, project: project, role: user!['role']),
        ),
      ),
    );
  }
}

class ProjectDialog extends StatefulWidget {
  const ProjectDialog({super.key});
  @override
  State<ProjectDialog> createState() => _ProjectDialogState();
}

class _ProjectDialogState extends State<ProjectDialog> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController(), customer = TextEditingController();
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
              'customer': customer.text.trim(),
            });
        },
        child: const Text('Anlegen'),
      ),
    ],
  );
}

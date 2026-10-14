import 'package:flutter/material.dart';

import 'admin_pages.dart';
import 'api.dart';
import 'project_page.dart';

void main() => runApp(const OfficeApp());

class OfficeApp extends StatelessWidget {
  final OfficeApi? api;
  const OfficeApp({super.key, this.api});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Smartplan Office',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff163d46)),
      scaffoldBackgroundColor: const Color(0xfff4f6f7),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
    ),
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
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Smartplan Office'),
      actions: [
        if (user != null) ...[
          IconButton(
            tooltip: 'Aktualisieren',
            onPressed: busy ? null : () => run(loadProjects),
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Abmelden',
            onPressed: busy ? null : logout,
            icon: const Icon(Icons.logout),
          ),
        ],
      ],
    ),
    body: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1080),
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            if (busy) const LinearProgressIndicator(),
            if (error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (user == null)
              Form(
                key: loginForm,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Ihr Büro. Ihre Projekte.',
                      style: TextStyle(
                        fontSize: 30,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 24),
                    TextFormField(
                      controller: email,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(labelText: 'E-Mail'),
                      validator: (v) =>
                          (v ?? '').trim().isEmpty ? 'E-Mail eingeben.' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: password,
                      obscureText: true,
                      autocorrect: false,
                      enableSuggestions: false,
                      onFieldSubmitted: (_) {
                        if (!busy) login();
                      },
                      decoration: const InputDecoration(labelText: 'Passwort'),
                      validator: (v) =>
                          (v ?? '').isEmpty ? 'Passwort eingeben.' : null,
                    ),
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: busy ? null : login,
                      child: const Text('Anmelden'),
                    ),
                  ],
                ),
              )
            else ...[
              Text(
                user!['email'],
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(roleLabels[user!['role']] ?? user!['role']),
              const SizedBox(height: 24),
              const Text(
                'Projekte',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              if (projects.isEmpty)
                const Text('Noch keine freigegebenen Projekte.'),
              for (final p in projects)
                Card(
                  child: ListTile(
                    title: Text(p['name']),
                    subtitle: Text(p['customer']),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: busy
                        ? null
                        : () => Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => ProjectPage(
                                api: api,
                                project: Map<String, dynamic>.from(p),
                                role: user!['role'],
                              ),
                            ),
                          ),
                  ),
                ),
              if (user!['role'] == 'owner') ...[
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: busy ? null : newProject,
                  icon: const Icon(Icons.add),
                  label: const Text('Projekt anlegen'),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: busy
                      ? null
                      : () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) =>
                                UsersPage(api: api, currentUserId: user!['id']),
                          ),
                        ),
                  icon: const Icon(Icons.people),
                  label: const Text('Benutzerverwaltung'),
                ),
                const SizedBox(height: 24),
                Text(
                  storage?['connected'] == true
                      ? 'OneDrive: Anmeldung gespeichert'
                      : storage?['configured'] == true
                      ? 'OneDrive: noch nicht verbunden'
                      : 'OneDrive: noch nicht eingerichtet',
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: busy || storage?['configured'] != true
                      ? null
                      : connectDrive,
                  icon: const Icon(Icons.cloud_outlined),
                  label: const Text('OneDrive Family verbinden'),
                ),
              ],
            ],
          ],
        ),
      ),
    ),
  );
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

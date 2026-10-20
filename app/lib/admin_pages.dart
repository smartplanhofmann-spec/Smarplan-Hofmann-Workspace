import 'package:flutter/material.dart';

import 'api.dart';
import 'design.dart';

class UsersPage extends StatefulWidget {
  final OfficeApi api;
  final String currentUserId;
  const UsersPage({super.key, required this.api, required this.currentUserId});
  @override
  State<UsersPage> createState() => _UsersPageState();
}

class _UsersPageState extends State<UsersPage> {
  List<dynamic> users = [];
  bool busy = false;
  String? error;

  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> refresh() => run(() async {
    final result = List<dynamic>.from(await widget.api.call('/api/users'));
    if (mounted) setState(() => users = result);
  });

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

  Future<void> edit([Map<String, dynamic>? user]) async {
    final values = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => UserDialog(
        user: user,
        ownAccount: user?['id'] == widget.currentUserId,
      ),
    );
    if (!mounted || values == null) return;
    await run(() async {
      await widget.api.call(
        user == null ? '/api/users' : '/api/users/${user['id']}',
        values,
      );
      final result = List<dynamic>.from(await widget.api.call('/api/users'));
      if (mounted) setState(() => users = result);
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Benutzerverwaltung'),
      actions: [
        IconButton(
          tooltip: 'Aktualisieren',
          onPressed: busy ? null : refresh,
          icon: const Icon(Icons.refresh_rounded),
        ),
        const SizedBox(width: 16),
      ],
    ),
    body: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1120),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 12, 24, 40),
          children: [
            PageHeading(
              eyebrow: 'Zusammenarbeit',
              title: 'Das Team.',
              subtitle: 'Menschen, Rollen und Zugänge. Klar geregelt.',
              action: FilledButton.icon(
                onPressed: busy ? null : () => edit(),
                icon: const Icon(Icons.person_add_outlined, size: 18),
                label: const Text('Benutzer anlegen'),
              ),
            ),
            const SizedBox(height: 30),
            if (busy)
              const Padding(
                padding: EdgeInsets.only(bottom: 20),
                child: LinearProgressIndicator(minHeight: 2),
              ),
            if (error != null) Notice(error!),
            OfficeSurface(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        'Alle Benutzer',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(width: 10),
                      StatusPill('${users.length}'),
                    ],
                  ),
                  const SizedBox(height: 20),
                  const Divider(),
                  if (!busy && users.isEmpty)
                    const EmptyState(
                      title: 'Keine Benutzer vorhanden.',
                      description: 'Legen Sie einen Zugang für Ihr Team an.',
                      icon: Icons.people_outline_rounded,
                    ),
                  for (final user in users)
                    Material(
                      color: Colors.transparent,
                      child: InkWell(
                        borderRadius: BorderRadius.circular(10),
                        onTap: busy
                            ? null
                            : () => edit(Map<String, dynamic>.from(user)),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            vertical: 18,
                            horizontal: 4,
                          ),
                          child: Row(
                            children: [
                              Container(
                                width: 42,
                                height: 42,
                                alignment: Alignment.center,
                                decoration: BoxDecoration(
                                  color: OfficeColors.canvas,
                                  borderRadius: BorderRadius.circular(13),
                                ),
                                child: Text(
                                  user['email']
                                      .toString()
                                      .substring(0, 1)
                                      .toUpperCase(),
                                  style: const TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w600,
                                    color: OfficeColors.muted,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      user['email'],
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      '${roleLabels[user['role']] ?? user['role']}${user['id'] == widget.currentUserId ? ' · Ihr Zugang' : ''}',
                                      style: const TextStyle(
                                        fontSize: 11,
                                        color: OfficeColors.muted,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 10),
                              StatusPill(
                                user['active'] == 1 ? 'Aktiv' : 'Gesperrt',
                                positive: user['active'] == 1,
                              ),
                              const SizedBox(width: 12),
                              const Icon(
                                Icons.chevron_right_rounded,
                                size: 18,
                                color: OfficeColors.muted,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class UserDialog extends StatefulWidget {
  final Map<String, dynamic>? user;
  final bool ownAccount;
  const UserDialog({super.key, this.user, this.ownAccount = false});
  @override
  State<UserDialog> createState() => _UserDialogState();
}

class _UserDialogState extends State<UserDialog> {
  final form = GlobalKey<FormState>();
  final email = TextEditingController();
  final password = TextEditingController();
  late String role;
  late bool active;

  @override
  void initState() {
    super.initState();
    email.text = widget.user?['email'] ?? '';
    role = widget.user?['role'] ?? 'technician';
    active = widget.user == null || widget.user!['active'] == 1;
  }

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    super.dispose();
  }

  void submit() {
    if (!form.currentState!.validate()) return;
    Navigator.pop(context, <String, dynamic>{
      if (widget.user == null) 'email': email.text.trim(),
      'role': role,
      if (widget.user != null) 'active': active,
      if (password.text.isNotEmpty) 'password': password.text,
    });
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.user == null ? 'Benutzer anlegen' : 'Benutzer bearbeiten',
    ),
    content: SizedBox(
      width: 460,
      child: Form(
        key: form,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: email,
                enabled: widget.user == null,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(labelText: 'E-Mail'),
                validator: (v) =>
                    RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
                        .hasMatch(v?.trim() ?? '')
                    ? null
                    : 'Gültige E-Mail-Adresse eingeben.',
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                initialValue: role,
                decoration: const InputDecoration(labelText: 'Rolle'),
                items: roleLabels.entries
                    .map(
                      (e) =>
                          DropdownMenuItem(value: e.key, child: Text(e.value)),
                    )
                    .toList(),
                onChanged: widget.ownAccount
                    ? null
                    : (v) => setState(() => role = v!),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: password,
                obscureText: true,
                autocorrect: false,
                enableSuggestions: false,
                decoration: InputDecoration(
                  labelText: widget.user == null
                      ? 'Passwort'
                      : 'Neues Passwort (optional)',
                ),
                validator: (v) {
                  if (widget.user != null && (v ?? '').isEmpty) return null;
                  return (v ?? '').length >= 12 && (v ?? '').length <= 512
                      ? null
                      : '12 bis 512 Zeichen verwenden.';
                },
              ),
              if (widget.user != null) ...[
                const SizedBox(height: 12),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Zugang aktiv'),
                  value: active,
                  onChanged: widget.ownAccount
                      ? null
                      : (v) => setState(() => active = v),
                ),
                const Text(
                  'Sperren, Rollenwechsel und Passwortwechsel beenden bestehende Sitzungen.',
                ),
              ],
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
      FilledButton(onPressed: submit, child: const Text('Speichern')),
    ],
  );
}

class AssignmentsPage extends StatefulWidget {
  final OfficeApi api;
  final Map<String, dynamic> project;
  const AssignmentsPage({super.key, required this.api, required this.project});
  @override
  State<AssignmentsPage> createState() => _AssignmentsPageState();
}

class _AssignmentsPageState extends State<AssignmentsPage> {
  List<dynamic> users = [];
  Set<String> assigned = {};
  bool busy = false;
  String? error;
  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> read() async {
    final all = List<dynamic>.from(await widget.api.call('/api/users'));
    final members = List<dynamic>.from(
      await widget.api.call(
        '/api/projects/${widget.project['id']}/assignments',
      ),
    );
    if (mounted)
      setState(() {
        users = all;
        assigned = members.map((u) => u['id'] as String).toSet();
      });
  }

  Future<void> refresh() => run(read);
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

  Future<void> change(Map<String, dynamic> user, bool value) => run(() async {
    await widget.api.call('/api/assignments', {
      'project_id': widget.project['id'],
      'user_id': user['id'],
      'remove': !value,
    });
    await read();
  });

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Projektzugriff'),
      actions: [
        IconButton(
          tooltip: 'Aktualisieren',
          onPressed: busy ? null : refresh,
          icon: const Icon(Icons.refresh_rounded),
        ),
        const SizedBox(width: 16),
      ],
    ),
    body: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1000),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 12, 24, 40),
          children: [
            PageHeading(
              eyebrow: 'Zusammenarbeit',
              title: 'Die richtigen Menschen.',
              subtitle: 'Projektzugriff für ${widget.project['name']}',
            ),
            const SizedBox(height: 28),
            const Notice(
              'Die Geschäftsführung sieht alle Projekte. Andere Rollen benötigen eine ausdrückliche Zuordnung.',
              error: false,
            ),
            if (busy)
              const Padding(
                padding: EdgeInsets.only(bottom: 20),
                child: LinearProgressIndicator(minHeight: 2),
              ),
            if (error != null) Notice(error!),
            OfficeSurface(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Zugriff verwalten',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Änderungen werden sofort übernommen.',
                    style: TextStyle(fontSize: 12, color: OfficeColors.muted),
                  ),
                  const SizedBox(height: 20),
                  if (!busy && users.where((u) => u['role'] != 'owner').isEmpty)
                    const EmptyState(
                      title: 'Noch keine weiteren Benutzer.',
                      description: 'Legen Sie zuerst einen Benutzer in der Benutzerverwaltung an.',
                      icon: Icons.people_outline_rounded,
                    ),
                  for (final user in users)
                    if (user['role'] != 'owner')
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Material(
                          color: assigned.contains(user['id'])
                              ? OfficeColors.blueTint
                              : const Color(0xfffafafa),
                          borderRadius: BorderRadius.circular(12),
                          child: CheckboxListTile(
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 8,
                            ),
                            controlAffinity: ListTileControlAffinity.leading,
                            title: Text(
                              user['email'],
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            subtitle: Padding(
                              padding: const EdgeInsets.only(top: 4),
                              child: Text(
                                '${roleLabels[user['role']]}${user['active'] == 1 ? '' : ' · Zugang gesperrt'}',
                                style: const TextStyle(
                                  fontSize: 11,
                                  color: OfficeColors.muted,
                                ),
                              ),
                            ),
                            value: assigned.contains(user['id']),
                            onChanged: busy
                                ? null
                                : (v) => change(
                                    Map<String, dynamic>.from(user),
                                    v!,
                                  ),
                          ),
                        ),
                      ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

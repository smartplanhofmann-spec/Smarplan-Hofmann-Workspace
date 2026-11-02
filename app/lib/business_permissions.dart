import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const businessPermissionLabels = <String, String>{
  'contacts.read': 'Kontakte lesen',
  'contacts.write': 'Kontakte bearbeiten',
  'projects.manage': 'Projekte verwalten',
  'documents.read': 'Projektdokumente lesen',
  'documents.write': 'Projektdokumente bearbeiten',
  'documents.classify': 'Dokumentzugriff einstufen',
  'finance.read': 'Finanzdaten lesen',
  'finance.write': 'Finanzdaten bearbeiten',
  'finance.issue': 'Belege festschreiben',
  'finance.approve': 'Kaufmännische Vorgänge freigeben',
  'personnel.read': 'Personaldaten lesen',
  'personnel.manage': 'Personal verwalten',
  'personnel.write': 'Personaldaten bearbeiten',
  'personnel.approve': 'Personalvorgänge freigeben',
  'personnel.export': 'Personaldaten exportieren',
  'planning.read': 'Planung lesen',
  'planning.write': 'Planung bearbeiten',
  'planning.override': 'Planungskonflikte freigeben',
  'time.own': 'Eigene Zeiten erfassen',
  'time.approve': 'Zeiten freigeben',
  'inventory.read': 'Material und Lager lesen',
  'inventory.write': 'Material und Lager bearbeiten',
  'privacy.manage': 'Datenschutzvorgänge verwalten',
  'settings.manage': 'Facheinstellungen verwalten',
  'portal.manage': 'Angebotsportal verwalten',
  'accounting.read': 'EÜR-Vorbereitung lesen',
  'accounting.prepare': 'Geldflüsse im Vorjournal bestätigen',
  'accounting.admin': 'Geldkonten verwalten',
};

const _roleLabels = {
  'manager': 'Projektleitung',
  'technician': 'Technik',
  'accountant': 'Buchhaltung',
};

class BusinessPermissionsPage extends StatefulWidget {
  const BusinessPermissionsPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessPermissionsPage> createState() =>
      _BusinessPermissionsPageState();
}

class _BusinessPermissionsPageState extends State<BusinessPermissionsPage> {
  List<Map<String, dynamic>> users = [], grants = [];
  String? userId, permission, error;
  String scope = '*';
  bool loading = false, ready = false;
  int epoch = 0;
  bool get mayRead => widget.session.can('settings.manage');
  bool get mayWrite =>
      ready && !loading && widget.session.canWrite('settings.manage');
  Map<String, String> get permissions => {
    for (final entry in businessPermissionLabels.entries)
      if ((entry.key != 'portal.manage' ||
              widget.session.hasFeature('offer_portal')) &&
          (!entry.key.startsWith('accounting.') ||
              (scope == '*' &&
                  widget.session.hasFeature('accounting_prejournal'))))
        entry.key: entry.value,
  };
  Map<String, String> get userChoices => {
    for (final user in users.where((user) => user['role'] != 'owner'))
      '${user['id']}':
          '${user['email']} · ${_roleLabels[user['role']] ?? user['role']}${user['active'] == false || user['active'] == 0 ? ' (inaktiv)' : ''}',
  };
  Map<String, String> get scopes => {
    '*': 'Global',
    for (final project in widget.session.projects)
      '${project['id']}': '${project['name']}',
  };

  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!mayRead) {
        epoch++;
        users = [];
        grants = [];
        userId = permission = null;
        ready = loading = false;
      } else if (permission != null && !permissions.containsKey(permission)) {
        permission = null;
      }
    });
  }

  Future<void> load() async {
    if (!mayRead) return;
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
      ready = false;
    });
    try {
      final result = await Future.wait([
        widget.session.read('/settings/permissions'),
        widget.session.legacyRead('/api/users'),
      ]);
      final loadedUsers = businessItems(result[1]);
      final loadedGrants = businessItems(result[0]);
      if (mounted && current == epoch && mayRead)
        setState(() {
          users = loadedUsers;
          grants = loadedGrants;
          if (!userChoices.containsKey(userId)) userId = null;
          ready = true;
        });
    } catch (e) {
      if (mounted && current == epoch && mayRead)
        setState(() {
          error = '$e';
          users = [];
          grants = [];
          ready = false;
        });
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> edit({Map<String, dynamic>? selected}) async {
    final user = selected?['user_id'] as String? ?? userId;
    final targetScope = selected?['scope'] as String? ?? scope;
    final targetPermission = selected?['permission'] as String? ?? permission;
    if (!mayWrite ||
        user == null ||
        targetPermission == null ||
        !userChoices.containsKey(user) ||
        !scopes.containsKey(targetScope) ||
        !permissions.containsKey(targetPermission))
      return;
    if (targetPermission.startsWith('accounting.') && targetScope != '*')
      return;
    final current = grants
        .where(
          (grant) =>
              grant['user_id'] == user &&
              grant['scope'] == targetScope &&
              grant['permission'] == targetPermission,
        )
        .firstOrNull;
    final revision = current?['revision'] as int? ?? 0;
    final key = 'permission-$user-$targetScope-$targetPermission';
    final session = widget.session;
    final pending = session.pendingEditorValues(key);
    final choices = <String, String>{
      'allow:$revision': 'Erlauben',
      'deny:$revision': 'Sperren',
      if (pending?['effect_revision'] is String)
        pending!['effect_revision'] as String:
            '${(pending['effect_revision'] as String).startsWith('allow:') ? 'Erlauben' : 'Sperren'} · noch unbestätigt',
    };
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        pendingKey: key,
        title: 'Fachrecht prüfen',
        readPermission: 'settings.manage',
        writePermission: 'settings.manage',
        saveLabel: 'Fachrecht speichern',
        initial: {
          'effect_revision': '${current?['effect'] ?? 'allow'}:$revision',
        },
        fields: [
          BusinessField(
            'effect_revision',
            '${permissions[targetPermission]} · ${userChoices[user]} · ${scopes[targetScope]}',
            type: BusinessInput.choice,
            required: true,
            choices: choices,
          ),
        ],
        onSave: (values) async {
          await session.load();
          if (session.error != null || session.loading) {
            throw const ApiException(
              0,
              'Die aktuellen Berechtigungen konnten noch nicht bestätigt werden. Bitte erneut versuchen.',
            );
          }
          if (!session.canWrite('settings.manage')) {
            throw const ApiException(
              403,
              'Die Berechtigung zum Verwalten der Fachrechte fehlt.',
            );
          }
          if (targetPermission == 'portal.manage' &&
              !session.hasFeature('offer_portal')) {
            throw const ApiException(
              403,
              'Das Angebotsportal ist auf diesem Server nicht freigegeben.',
            );
          }
          if (targetPermission.startsWith('accounting.') &&
              (targetScope != '*' ||
                  !session.hasFeature('accounting_prejournal'))) {
            throw const ApiException(
              403,
              'EÜR-Fachrechte benötigen die globale Freigabe dieses Funktionsstands.',
            );
          }
          final freshUsers = businessItems(
            await session.legacyRead('/api/users'),
          );
          if (!session.canWrite('settings.manage') ||
              !freshUsers.any(
                (entry) => entry['id'] == user && entry['role'] != 'owner',
              )) {
            throw const ApiException(
              403,
              'Der ausgewählte Benutzer darf nicht über diesen Editor geändert werden.',
            );
          }
          final match = RegExp(r'^(allow|deny):(\d+)$')
              .firstMatch('${values['effect_revision']}');
          if (match == null)
            throw const FormatException(
              'Bitte eine gültige Entscheidung auswählen.',
            );
          await session.command(key, '/settings/permissions', {
            'user_id': user,
            'permission': targetPermission,
            'scope': targetScope,
            'effect': match.group(1),
            'revision': int.parse(match.group(2)!),
          });
        },
      ),
    );
    if (mounted && mayRead) await load();
  }

  Widget choice(
    String key,
    String label,
    String? value,
    Map<String, String> options,
    ValueChanged<String?> onChanged,
  ) => DropdownButtonFormField<String>(
    key: ValueKey('permission-$key-$value'),
    initialValue: value,
    decoration: InputDecoration(labelText: label),
    isExpanded: true,
    items: [
      for (final entry in options.entries)
        DropdownMenuItem(
          value: entry.key,
          child: Text(entry.value, overflow: TextOverflow.ellipsis),
        ),
    ],
    onChanged: mayWrite ? onChanged : null,
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Fachrechte'),
      actions: [
        IconButton(
          tooltip: 'Fachrechte aktualisieren',
          onPressed: loading || !mayRead ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !mayRead
        ? const BusinessEmpty(
            'Kein Zugriff',
            'Fachrechte benötigen Administrationsrechte.',
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Text(
                'Rechte gelten zusätzlich zur Benutzerrolle. Eine Projektregel ersetzt keine Projektzuweisung. Globale Verwaltungsfunktionen benötigen den globalen Umfang.',
              ),
              const SizedBox(height: 16),
              if (error != null) Notice(error!, error: true),
              if (loading) const LinearProgressIndicator(),
              if (widget.session.readonly)
                const Notice(
                  'Die Fachrechte sind im Rückkehrmodus nur lesbar.',
                ),
              if (ready) ...[
                if (userChoices.isEmpty)
                  const Notice(
                    'Die Geschäftsführung behält vollständige Fachrechte. Für weitere Regeln wird ein anderer Benutzer benötigt.',
                  ),
                choice(
                  'user',
                  'Benutzer',
                  userId,
                  userChoices,
                  (value) => setState(() => userId = value),
                ),
                const SizedBox(height: 16),
                choice(
                  'scope',
                  'Umfang',
                  scope,
                  scopes,
                  (value) => setState(() {
                    scope = value ?? '*';
                    if (!permissions.containsKey(permission)) permission = null;
                  }),
                ),
                const SizedBox(height: 16),
                choice(
                  'right',
                  'Fachrecht',
                  permission,
                  permissions,
                  (value) => setState(() => permission = value),
                ),
                const SizedBox(height: 16),
                Align(
                  alignment: Alignment.centerLeft,
                  child: FilledButton.icon(
                    onPressed: mayWrite && userId != null && permission != null
                        ? () => edit()
                        : null,
                    icon: const Icon(Icons.rule_outlined),
                    label: const Text('Regel prüfen'),
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  'Gespeicherte Regeln',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                if (grants.isEmpty)
                  const BusinessEmpty(
                    'Noch keine zusätzlichen Regeln',
                    'Es gelten die vorhandenen Rollenrechte und Projektzuweisungen.',
                  ),
                for (final grant in grants)
                  Card(
                    child: ListTile(
                      title: Text(
                        businessPermissionLabels[grant['permission']] ??
                            '${grant['permission']}',
                      ),
                      subtitle: Text(
                        '${userChoices[grant['user_id']] ?? 'Benutzer nicht verfügbar'}\n${scopes[grant['scope']] ?? 'Projekt nicht verfügbar'} · ${grant['effect'] == 'allow' ? 'Erlaubt' : 'Gesperrt'}',
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap:
                          mayWrite &&
                              userChoices.containsKey(grant['user_id']) &&
                              scopes.containsKey(grant['scope']) &&
                              (!'${grant['permission']}'.startsWith(
                                    'accounting.',
                                  ) ||
                                  grant['scope'] == '*') &&
                              permissions.containsKey(grant['permission'])
                          ? () => edit(selected: grant)
                          : null,
                    ),
                  ),
              ],
            ],
          ),
  );
}

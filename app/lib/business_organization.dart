import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'design.dart';

const organizationNeeds = {
  'has_employees': 'Wir beschäftigen Mitarbeiter',
  'uses_inventory': 'Wir verwalten Material und Lagerbestände',
  'project_work': 'Wir arbeiten mit Projekten und Einsatzplanung',
  'uses_finance': 'Wir benötigen Belege und Finanzübersichten',
  'works_with_tax_advisor': 'Wir arbeiten mit einem Steuerberater',
};
const organizationModules = {
  'personnel': 'Personal',
  'material': 'Material',
  'planning': 'Einsatzplanung',
  'documents': 'Belege',
  'finance': 'Finanzen',
};

class BusinessOrganizationPanel extends StatefulWidget {
  const BusinessOrganizationPanel({
    super.key,
    required this.session,
    this.onOpenSection,
  });
  final BusinessSession session;
  final ValueChanged<String>? onOpenSection;

  @override
  State<BusinessOrganizationPanel> createState() =>
      _BusinessOrganizationPanelState();
}

class _BusinessOrganizationPanelState extends State<BusinessOrganizationPanel> {
  Map<String, dynamic>? current;
  final needs = <String, bool>{};
  final visibility = <String, String>{};
  final enabled = <String, bool>{};
  bool busy = false, uncertain = false;
  String? error, confirmation;

  bool get mayRead =>
      widget.session.can('settings.manage') &&
      widget.session.hasFeature('organization_modules');
  bool get mayEdit =>
      mayRead &&
      widget.session.canWrite('settings.manage') &&
      !busy &&
      !uncertain;

  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!mayRead) {
      current = null;
      needs.clear();
      visibility.clear();
      enabled.clear();
    }
    setState(() {});
  }

  void apply(Map<String, dynamic> value) {
    final suppliedNeeds = businessMap(value['needs']);
    final suppliedModules = businessMap(value['modules']);
    if (value['revision'] is! int ||
        organizationNeeds.keys.any((key) => suppliedNeeds[key] is! bool) ||
        organizationModules.keys.any((key) {
          final item = businessMap(suppliedModules[key]);
          return item['enabled'] is! bool ||
              item['visible'] is! bool ||
              item['suggested'] is! bool ||
              (item['visibility_override'] != null &&
                  item['visibility_override'] is! bool);
        })) {
      throw const FormatException(
        'Die Unternehmenseinstellungen sind unvollständig. Bitte neu laden.',
      );
    }
    current = value;
    for (final key in organizationNeeds.keys) {
      needs[key] = suppliedNeeds[key] as bool;
    }
    for (final key in organizationModules.keys) {
      final item = businessMap(suppliedModules[key]);
      visibility[key] = item['visibility_override'] == null
          ? 'auto'
          : item['visibility_override'] == true
          ? 'show'
          : 'hide';
      enabled[key] = item['enabled'] as bool;
    }
  }

  Future<void> load() async {
    if (!mayRead || busy || uncertain) return;
    setState(() {
      busy = true;
      error = null;
      confirmation = null;
    });
    try {
      final value = businessMap(await widget.session.read('/organization'));
      if (mounted && mayRead) setState(() => apply(value));
    } catch (e) {
      if (mounted && mayRead) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> save() async {
    if (!mayRead ||
        !widget.session.canWrite('settings.manage') ||
        current == null ||
        busy)
      return;
    setState(() {
      busy = true;
      error = null;
      confirmation = null;
    });
    try {
      final value = businessMap(
        await widget.session.command(
          'organization-${current!['revision']}',
          '/organization',
          {
            'revision': current!['revision'],
            'needs': Map<String, bool>.from(needs),
            'modules': {
              for (final key in organizationModules.keys)
                key: {
                  'visible': visibility[key] == 'auto'
                      ? null
                      : visibility[key] == 'show',
                  'enabled': enabled[key],
                },
            },
          },
        ),
      );
      if (!mounted || !mayRead) return;
      setState(() {
        apply(value);
        uncertain = false;
        confirmation = 'Unternehmensbedarf und Module gespeichert.';
      });
      await widget.session.load();
    } on ApiException catch (e) {
      if (mounted && mayRead)
        setState(() {
          uncertain = e.status == 0 || e.status >= 500 || e.status == 429;
          error = e.message;
        });
    } catch (e) {
      if (mounted && mayRead) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  bool canOpen(String key) {
    const required = {
      'personnel': ('planning', 'time.own'),
      'material': ('inventory', 'inventory.read'),
      'planning': ('planning', 'planning.read'),
      'documents': ('documents', 'finance.read'),
      'finance': ('finance', 'finance.read'),
    };
    final rights = required[key]!;
    return widget.onOpenSection != null &&
        widget.session.hasModule(rights.$1) &&
        widget.session.can(rights.$2);
  }

  Widget module(String key, String label) {
    final saved = businessMap(businessMap(current!['modules'])[key]);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text(
            'Vorschlag: ${saved['suggested'] == true ? 'anzeigen' : 'ausblenden'}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            key: ValueKey(
              'organization-visible-$key-${current!['revision']}-${visibility[key]}',
            ),
            initialValue: visibility[key],
            isExpanded: true,
            decoration: InputDecoration(labelText: '$label in der Navigation'),
            items: const [
              DropdownMenuItem(value: 'auto', child: Text('Automatisch')),
              DropdownMenuItem(value: 'show', child: Text('Immer anzeigen')),
              DropdownMenuItem(value: 'hide', child: Text('Ausblenden')),
            ],
            onChanged: mayEdit
                ? (value) => setState(() {
                    visibility[key] = value!;
                    confirmation = null;
                  })
                : null,
          ),
          SwitchListTile.adaptive(
            key: ValueKey('organization-enabled-$key'),
            contentPadding: EdgeInsets.zero,
            title: Text('$label fachlich aktiv'),
            subtitle: Text(
              enabled[key] == true
                  ? 'Neue Vorgänge gemäß Benutzerrechten möglich.'
                  : 'Historie und Exporte bleiben lesbar. Änderungen sind gesperrt.',
            ),
            value: enabled[key] ?? true,
            onChanged: mayEdit
                ? (value) => setState(() {
                    enabled[key] = value;
                    confirmation = null;
                  })
                : null,
          ),
          if (canOpen(key))
            TextButton.icon(
              key: ValueKey('organization-open-$key'),
              onPressed: busy || uncertain
                  ? null
                  : () => widget.onOpenSection!(key),
              icon: const Icon(Icons.open_in_new),
              label: Text('$label öffnen'),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!mayRead) return const SizedBox();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Unternehmen und Module',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            const Text(
              'Passen Sie die Navigation an Ihren Betrieb an. Ausgeblendete '
              'Bereiche behalten ihre Daten. Benutzerrechte gelten unabhängig '
              'von Sichtbarkeit und Aktivierung.',
            ),
            const SizedBox(height: 16),
            if (busy) const LinearProgressIndicator(),
            if (error != null) Notice(error!, error: true),
            if (confirmation != null) Notice(confirmation!),
            if (uncertain)
              const Notice(
                'Die Antwort ist noch nicht bestätigt. Wiederholen Sie das '
                'Speichern unverändert, bevor Sie weitere Angaben bearbeiten.',
              ),
            if (current != null) ...[
              for (final need in organizationNeeds.entries)
                SwitchListTile.adaptive(
                  key: ValueKey('organization-need-${need.key}'),
                  contentPadding: EdgeInsets.zero,
                  title: Text(need.value),
                  value: needs[need.key] ?? false,
                  onChanged: mayEdit
                      ? (value) => setState(() {
                          needs[need.key] = value;
                          confirmation = null;
                        })
                      : null,
                ),
              if (current!['active_employee_count'] is int)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    '${current!['active_employee_count']} aktive Mitarbeiter '
                    'sind bereits hinterlegt. Vorschläge werden beim Speichern '
                    'und bei Änderungen des Mitarbeiterbestands aktualisiert.',
                  ),
                ),
              const Divider(height: 32),
              for (final item in organizationModules.entries)
                module(item.key, item.value),
            ],
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                if (current != null)
                  FilledButton.icon(
                    key: const ValueKey('organization-save'),
                    onPressed:
                        busy || !widget.session.canWrite('settings.manage')
                        ? null
                        : save,
                    icon: const Icon(Icons.save_outlined),
                    label: Text(
                      uncertain
                          ? 'Speichern erneut bestätigen'
                          : 'Module speichern',
                    ),
                  ),
                OutlinedButton.icon(
                  onPressed: busy || uncertain ? null : load,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Gespeicherten Stand laden'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

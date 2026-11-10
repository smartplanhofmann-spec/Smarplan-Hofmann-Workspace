import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'design.dart';

Map<String, dynamic> installationContextView(dynamic raw) {
  final v = businessMap(raw);
  const keys = {
    'schema_version',
    'status',
    'source_commit',
    'api_compatibility_version',
  };
  final compatibility = v['api_compatibility_version'],
      source = v['source_commit'];
  if (v.length != keys.length ||
      !v.keys.every(keys.contains) ||
      v['schema_version'] is! int ||
      v['schema_version'] != 1 ||
      !['recorded', 'unrecorded'].contains(v['status']) ||
      compatibility is! String ||
      compatibility.isEmpty ||
      compatibility.length > 64 ||
      !RegExp(r'^[a-zA-Z0-9]').hasMatch(compatibility) ||
      RegExp(r'[^a-zA-Z0-9._+-]').hasMatch(compatibility) ||
      (v['status'] == 'recorded'
          ? source is! String ||
                source.length != 40 ||
                RegExp(r'[^a-f0-9]').hasMatch(source)
          : source != null)) {
    throw const ApiException(
      409,
      'Der Installationsnachweis ist unvollständig. Bitte neu laden.',
    );
  }
  return {
    'recorded': v['status'] == 'recorded',
    'source': source,
    'compatibility': compatibility,
  };
}

Future<Map<String, dynamic>> readInstallationContext(
  BusinessSession session,
) async {
  await session.load();
  final generation = session.generation;
  bool available() =>
      session.can('settings.manage') &&
      session.hasFeature('installation_context') &&
      session.generation == generation;
  if (!available())
    throw const ApiException(
      403,
      'Die aktuelle Freigabe für den Serverstand fehlt.',
    );
  final value = installationContextView(await session.read('/installation'));
  await session.load();
  if (!available())
    throw const ApiException(
      403,
      'Die aktuelle Freigabe für den Serverstand fehlt.',
    );
  return value;
}

class BusinessInstallationPanel extends StatefulWidget {
  const BusinessInstallationPanel({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessInstallationPanel> createState() =>
      _BusinessInstallationPanelState();
}

class _BusinessInstallationPanelState extends State<BusinessInstallationPanel> {
  bool busy = false;
  String? error;
  Future<void> open() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    final session = widget.session;
    try {
      final value = await readInstallationContext(session),
          generation = session.generation;
      if (!mounted ||
          !identical(session, widget.session) ||
          !session.can('settings.manage'))
        return;
      await showDialog<void>(
        context: context,
        builder: (_) => ListenableBuilder(
          listenable: session,
          builder: (context, _) {
            final current =
                session.can('settings.manage') &&
                session.hasFeature('installation_context') &&
                session.generation == generation;
            return AlertDialog(
              title: const Text('Installierter Serverstand'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: current
                      ? [
                          Text(
                            value['recorded'] == true
                                ? 'Quellstand beim Paketbau festgehalten.'
                                : 'Für diese laufende Installation ist kein verlässlicher Paketstand erfasst. Der Stand wird nicht aus einer Arbeitskopie abgeleitet.',
                          ),
                          if (value['recorded'] == true) ...[
                            const SizedBox(height: 12),
                            const Text('Installierter Quellstand:'),
                            SelectableText(value['source']),
                          ],
                          const SizedBox(height: 12),
                          Text('API-Kompatibilität: ${value['compatibility']}'),
                          const SizedBox(height: 12),
                          const Text(
                            'Die Kompatibilitätskennung ist keine App-Buildnummer. Eine neuere App aktualisiert den verbundenen Server nicht automatisch.',
                          ),
                        ]
                      : [
                          const Text(
                            'Der Serverstand ist mit dem aktuellen Zugang nicht mehr verfügbar.',
                          ),
                        ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Schließen'),
                ),
              ],
            );
          },
        ),
      );
    } catch (e) {
      if (mounted &&
          identical(session, widget.session) &&
          session.can('settings.manage'))
        setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.session,
    builder: (context, _) =>
        !widget.session.can('settings.manage') ||
            !widget.session.hasFeature('installation_context')
        ? const SizedBox.shrink()
        : Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Version und Support',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Den Paketstand der verbundenen Serverinstallation lesen.',
                  ),
                  if (error != null) Notice(error!, error: true),
                  const SizedBox(height: 12),
                  OutlinedButton(
                    onPressed: busy ? null : open,
                    child: const Text('Serverstand anzeigen'),
                  ),
                ],
              ),
            ),
          ),
  );
}

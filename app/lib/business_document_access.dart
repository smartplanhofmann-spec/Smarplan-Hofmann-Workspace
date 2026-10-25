import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const documentClassNames = {
  'unclassified': 'Noch nicht freigegeben',
  'operational': 'Projektteam · operativ',
  'financial': 'Finanzberechtigte',
  'personnel': 'Personalberechtigte',
  'restricted': 'Nur Geschäftsführung',
};

class BusinessDocumentAccessPage extends StatefulWidget {
  const BusinessDocumentAccessPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessDocumentAccessPage> createState() =>
      _BusinessDocumentAccessPageState();
}

class _BusinessDocumentAccessPageState
    extends State<BusinessDocumentAccessPage> {
  List<Map<String, dynamic>> documents = [];
  String? error;
  bool loading = true;
  int epoch = 0;
  bool get allowed => widget.session.can('documents.classify');
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!allowed) {
        epoch++;
        documents = [];
      }
      setState(() {});
    }
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    super.dispose();
  }

  String path(Map<String, dynamic> d) =>
      '/documents/${d['kind']}/${d['id']}/classification';
  Future<void> load() async {
    final current = ++epoch;
    if (!allowed || widget.session.projectId == null) {
      setState(() => loading = false);
      return;
    }
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final project = widget.session.projectId;
      final replies = await Future.wait([
        widget.session.legacyRead('/api/projects/$project/links'),
        widget.session.legacyRead('/api/projects/$project/mail-attachments'),
      ]);
      final links = (replies[0] as List)
          .map(businessMap)
          .map((r) => {...r, 'kind': 'link'});
      final files = (businessMap(replies[1])['files'] as List? ?? [])
          .map(businessMap)
          .map((r) => {...r, 'kind': 'mail'});
      final rows = [...links, ...files];
      final result = <Map<String, dynamic>>[];
      for (var index = 0; index < rows.length; index += 4) {
        final group = await Future.wait(
          rows
              .skip(index)
              .take(4)
              .map(
                (r) async => {
                  ...r,
                  'release': businessMap(await widget.session.read(path(r))),
                },
              ),
        );
        if (!mounted || current != epoch || !allowed) return;
        result.addAll(group);
      }
      if (mounted && current == epoch && allowed)
        setState(() => documents = result);
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> classify(Map<String, dynamic> document) async {
    if (!widget.session.canWrite('documents.classify')) return;
    final release = businessMap(document['release']);
    final fingerprint = release['source_fingerprint'];
    if (fingerprint is! String ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch(fingerprint)) {
      setState(
        () => error = 'Die Freigabe kann noch nicht sicher an diese Fassung gebunden werden. Bitte die Seite nach dem Serverupdate neu laden.',
      );
      return;
    }
    var stale = false;
    final financialFloor =
        document['kind'] == 'link' &&
        ['offer', 'invoice'].contains(document['category']);
    final options = {
      for (final e in documentClassNames.entries)
        if (e.key != 'unclassified' &&
            (!financialFloor || ['financial', 'restricted'].contains(e.key)))
          e.key: e.value,
    };
    final initial = release['classification'] == 'unclassified'
        ? 'restricted'
        : release['classification'];
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        readPermission: 'documents.classify',
        writePermission: 'documents.classify',
        session: widget.session,
        title: 'Freigabe der geprüften Fassung',
        saveLabel: 'Freigabe speichern',
        initial: {'classification': initial},
        fields: [
          BusinessField(
            'classification',
            financialFloor ? 'Finanzunterlage freigeben für' : 'Freigeben für',
            type: BusinessInput.choice,
            required: true,
            choices: options,
          ),
        ],
        onSave: (values) async {
          if (!mounted || !widget.session.canWrite('documents.classify'))
            throw const ApiException(
              403,
              'Die Freigabe ist nicht mehr verfügbar.',
            );
          if (stale)
            throw const ApiException(
              409,
              'Die Quelle wurde geändert. Bitte schließen, neu laden und die aktuelle Fassung erneut prüfen.',
            );
          try {
            await widget.session.command(
              'release-${document['kind']}-${document['id']}-${release['revision']}-$fingerprint',
              path(document),
              {
                'revision': release['revision'],
                'expected_source_fingerprint': fingerprint,
                ...values,
              },
            );
          } on ApiException catch (e) {
            if (e.status == 409) {
              stale = true;
              throw const ApiException(
                409,
                'Die Quelle oder Freigabe wurde geändert. Bitte schließen, neu laden und die aktuelle Fassung erneut prüfen.',
              );
            }
            rethrow;
          }
        },
      ),
    );
    if (mounted) await load();
  }

  @override
  Widget build(BuildContext context) {
    if (!allowed)
      return const BusinessEmpty(
        'Freigaben nicht verfügbar',
        'Dokumentfreigaben benötigen eine eigene Berechtigung.',
        icon: Icons.lock_outline,
      );
    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Wrap(
            spacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                'Unterlagen freigeben',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              IconButton(
                tooltip: 'Freigaben neu laden',
                onPressed: loading ? null : load,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 12),
          const Notice(
            'Neue Mailoriginale und geänderte Links bleiben zunächst geschützt. Prüfen Sie die Quelle, bevor Sie genau diese Fassung für das Projektteam freigeben. Angebote und Rechnungen bleiben Finanzunterlagen.',
          ),
          if (error != null) Notice(error!, error: true),
          if (loading) const LinearProgressIndicator(),
          if (!loading && documents.isEmpty && error == null)
            const BusinessEmpty(
              'Keine prüfbaren Unterlagen',
              'Für Ihren Zugang wurden keine Mailoriginale oder Projektlinks zurückgegeben.',
            ),
          for (final d in documents)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${d['filename'] ?? d['title'] ?? 'Unterlage'}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (d['kind'] == 'mail')
                      Text('E-Mail: ${d['subject'] ?? ''}'),
                    if (d['kind'] == 'link')
                      SelectableText('${d['url'] ?? ''}'),
                    const SizedBox(height: 8),
                    Text(
                      businessMap(d['release'])['release_current'] != true
                          ? 'Noch nicht freigegeben / nach Änderung erneut prüfen'
                          : documentClassNames[businessMap(
                                  d['release'],
                                )['effective_classification']] ??
                                'Geschützt',
                    ),
                    if (widget.session.canWrite('documents.classify'))
                      TextButton.icon(
                        onPressed: () => classify(d),
                        icon: const Icon(Icons.admin_panel_settings_outlined),
                        label: const Text('Freigabe prüfen'),
                      ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

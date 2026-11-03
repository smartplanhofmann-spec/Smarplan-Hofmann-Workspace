import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_documentation.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;

Map<String, dynamic> assetOriginValues(
  Map<String, dynamic> source,
  Map<String, dynamic> values, {
  Map<String, dynamic>? asset,
}) {
  if (source['receipt_id'] is! String ||
      !RegExp(r'^[a-f0-9]{32}$').hasMatch(source['receipt_id']) ||
      source['line_index'] is! int ||
      source['line_index'] < 0 ||
      source['document_accessible'] != true ||
      source['document'] is! Map) {
    throw const ApiException(
      400,
      'Eine Lieferposition mit zugänglichem Original auswählen.',
    );
  }
  final issues = businessItems(source['issues']);
  if (!issues.any((row) => row['id'] == values['issue_movement_id'])) {
    throw const ApiException(400, 'Eine passende Materialentnahme auswählen.');
  }
  final amount = '${values['quantity'] ?? ''}'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,12}(?:\.\d{1,4})?$').hasMatch(amount) ||
      RegExp(r'^0*(?:\.0*)?$').hasMatch(amount)) {
    throw const ApiException(
      400,
      'Eine positive Menge mit höchstens vier Nachkommastellen eingeben.',
    );
  }
  if (values['confirmed'] != true) {
    throw const ApiException(
      400,
      'Die tatsächliche Geräteherkunft ausdrücklich bestätigen.',
    );
  }
  final result = <String, dynamic>{
    'receipt_id': source['receipt_id'],
    'line_index': source['line_index'],
    'issue_movement_id': values['issue_movement_id'],
    'quantity': amount,
    'confirmed': true,
  };
  if (asset != null) {
    result['asset_revision'] = asset['revision'];
  } else {
    if ('${values['name'] ?? ''}'.trim().isEmpty ||
        '${values['serial_number'] ?? ''}'.trim().isEmpty) {
      throw const ApiException(400, 'Gerätename und Seriennummer eingeben.');
    }
    result['asset'] = {
      for (final field in [
        'name',
        'serial_number',
        'asset_type',
        'location',
        'notes',
      ])
        field: '${values[field] ?? ''}'.trim(),
    };
  }
  return result;
}

/// The existing asset remains the service-history identity. Delivery evidence is
/// a separate immutable link; this page never creates inventory or cost entries.
class BusinessAssetProvenancePage extends StatefulWidget {
  const BusinessAssetProvenancePage({
    super.key,
    required this.session,
    this.asset,
  });
  final BusinessSession session;
  final Map<String, dynamic>? asset;
  @override
  State<BusinessAssetProvenancePage> createState() =>
      _BusinessAssetProvenancePageState();
}

class _BusinessAssetProvenancePageState
    extends State<BusinessAssetProvenancePage> {
  late final String project = widget.session.projectId ?? '';
  List<Map<String, dynamic>> sources = [], history = [];
  Map<String, dynamic>? origin;
  bool busy = false, choosing = false;
  int epoch = 0, offset = 0;
  int? nextOffset;
  String? error;
  MailAttachmentPreviewController? preview;
  bool get allowed =>
      project.isNotEmpty &&
      widget.session.projectId == project &&
      widget.session.hasFeature('asset_delivery_provenance') &&
      widget.session.can('documents.read') &&
      widget.session.can('inventory.read');
  bool get writable =>
      allowed &&
      widget.session.canWrite('documents.write') &&
      widget.session.canWrite('inventory.write') &&
      widget.session.sectionEnabled('material');

  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (!mounted) return;
    if (!allowed) {
      epoch++;
      sources = [];
      history = [];
      origin = null;
      preview?.revoke();
      busy = false;
    }
    setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    preview?.revoke();
    super.dispose();
  }

  Future<void> load() async {
    if (!allowed) return;
    final captured = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (widget.asset != null && !choosing) {
        Map<String, dynamic>? result;
        try {
          result = businessMap(
            await widget.session.read('/assets/${widget.asset!['id']}/origin'),
          );
        } on ApiException catch (e) {
          if (e.status != 404) rethrow;
        }
        final visits = result == null
            ? <Map<String, dynamic>>[]
            : businessItems(
                await widget.session.read(
                  widget.session.query('/maintenance/history', {
                    'asset_id': '${widget.asset!['id']}',
                  }),
                ),
              );
        if (!mounted || captured != epoch || !allowed) return;
        setState(() {
          origin = result;
          history = visits;
        });
      } else {
        final result = businessMap(
          await widget.session.read(
            widget.session.query('/assets/origin-sources', {
              'limit': '25',
              'offset': '$offset',
            }),
          ),
        );
        if (!mounted || captured != epoch || !allowed) return;
        setState(() {
          sources = businessItems(result['items']);
          nextOffset = result['next_offset'] as int?;
        });
      }
    } catch (e) {
      if (mounted && captured == epoch && allowed) setState(() => error = '$e');
    } finally {
      if (mounted && captured == epoch) setState(() => busy = false);
    }
  }

  String commandKey(Map<String, dynamic> source) =>
      'asset-origin-${widget.asset?['id'] ?? project}-${source['receipt_id']}-${source['line_index']}';

  Future<void> create(Map<String, dynamic> source) async {
    if (!writable) return;
    final asset = widget.asset;
    final key = commandKey(source);
    final path = asset == null
        ? '/assets/from-delivery'
        : '/assets/${asset['id']}/origin';
    final pending = widget.session.pendingCommandValues(key, path: path);
    final issues = {
      for (final row in businessItems(source['issues']))
        '${row['id']}':
            'Entnahme ${row['sequence_number']} · noch ${row['available_quantity']} ${source['article']['unit']}',
    };
    if (pending != null && !issues.containsKey(pending['issue_movement_id'])) {
      issues['${pending['issue_movement_id']}'] =
          'Gespeicherte Entnahme des unbestätigten Vorgangs';
    }
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: asset == null
            ? 'Gerät aus Lieferung anlegen'
            : 'Lieferherkunft zuordnen',
        readPermission: 'documents.read',
        writePermission: 'inventory.write',
        readAllowed: () => allowed,
        pendingKey: key,
        saveLabel: 'Herkunft verbindlich bestätigen',
        fields: [
          if (asset == null) ...[
            BusinessField(
              'name',
              'Gerät',
              required: true,
              initial: source['article']['name'],
            ),
            const BusinessField(
              'serial_number',
              'Seriennummer',
              required: true,
            ),
            const BusinessField('asset_type', 'Anlagentyp'),
            const BusinessField('location', 'Standort / Raum'),
            const BusinessField(
              'notes',
              'Hinweise',
              type: BusinessInput.multiline,
            ),
          ],
          BusinessField(
            'issue_movement_id',
            'Tatsächliche Materialentnahme',
            type: BusinessInput.choice,
            required: true,
            choices: issues,
          ),
          const BusinessField(
            'quantity',
            'Zugeordnete Menge',
            type: BusinessInput.decimal,
            required: true,
            initial: '1',
          ),
          const BusinessField(
            'confirmed',
            'Ich bestätige die tatsächliche Herkunft dieses Geräts aus der genannten Lieferung und Entnahme.',
            type: BusinessInput.toggle,
            required: true,
            initial: false,
          ),
        ],
        onSave: (values) async {
          if (!writable)
            throw const ApiException(
              403,
              'Keine aktuelle Schreibfreigabe für diese Geräteherkunft.',
            );
          final frozen = widget.session.pendingCommandValues(key, path: path);
          final body =
              frozen ??
              {
                ...assetOriginValues(source, values, asset: asset),
                if (asset == null) 'project_id': project,
              };
          await widget.session.command(key, path, body);
        },
      ),
    );
    if (mounted) await load();
  }

  Future<void> attach(Map<String, dynamic> source) async {
    if (!writable) return;
    final captured = epoch;
    try {
      final media =
          businessItems(
                await widget.session.read(widget.session.query('/media')),
              )
              .where(
                (item) =>
                    item['status'] == 'ready' &&
                    ['document', 'site_photo'].contains(item['purpose']),
              )
              .toList();
      if (!mounted || captured != epoch || !writable) return;
      if (media.isEmpty) {
        setState(
          () => error = 'Das Original zuerst im selben Projekt unter Fotos und Dokumentation hochladen. Danach hier auswählen.',
        );
        return;
      }
      final path = '/purchasing/receipts/${source['receipt_id']}/document';
      final key = 'delivery-document-${source['receipt_id']}';
      await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (_) => BusinessEditor(
          session: widget.session,
          title: 'Original-Lieferschein zuordnen',
          readPermission: 'documents.read',
          writePermission: 'inventory.write',
          readAllowed: () => allowed,
          pendingKey: key,
          saveLabel: 'Original verbindlich zuordnen',
          fields: [
            BusinessField(
              'media_id',
              'Original des Lieferscheins',
              type: BusinessInput.choice,
              required: true,
              choices: {
                for (final item in media)
                  '${item['id']}': '${item['filename']}',
              },
            ),
            const BusinessField(
              'confirmed',
              'Ich habe Original und Wareneingang geprüft und bestätige die dauerhafte Zuordnung.',
              type: BusinessInput.toggle,
              required: true,
              initial: false,
            ),
          ],
          onSave: (values) async {
            if (!writable)
              throw const ApiException(403, 'Keine aktuelle Schreibfreigabe.');
            await widget.session.command(
              key,
              path,
              widget.session.pendingCommandValues(key, path: path) ?? values,
            );
          },
        ),
      );
      if (mounted) await load();
    } catch (e) {
      if (mounted && allowed) setState(() => error = '$e');
    }
  }

  Future<void> original(Map<String, dynamic> source) async {
    if (!allowed || busy) return;
    final captured = epoch;
    setState(() => busy = true);
    try {
      final document = businessMap(
        await widget.session.read(
          '/purchasing/receipts/${source['receipt_id']}/document',
        ),
      );
      final metadata = businessMap(document['original']);
      final path = '${document['download_path']}';
      if (!RegExp(r'^/media/[a-f0-9]{32}/content$').hasMatch(path))
        throw const ApiException(0, 'Ungültiger Originalpfad.');
      final bytes = await widget.session.api.bytes(
        widget.session.path(path),
        mediaType: '${metadata['media_type']}',
      );
      final hash = (await Sha256().hash(bytes)).bytes
          .map((value) => value.toRadixString(16).padLeft(2, '0'))
          .join();
      if (!mounted || captured != epoch || !allowed) return;
      if (hash != metadata['sha256'] || bytes.length != metadata['size'])
        throw const ApiException(
          0,
          'Die Originaldatei stimmt nicht mit der gespeicherten Prüfsumme überein.',
        );
      final controller = MailAttachmentPreviewController(
        VerifiedMailAttachment(
          bytes: bytes,
          filename: '${metadata['filename']}',
          mediaType: '${metadata['media_type']}',
          sha256: hash,
        ),
      );
      preview = controller;
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => MailAttachmentPreviewPage(
            controller: controller,
            mayView: () => mounted && captured == epoch && allowed,
            exporter: exportMailAttachment,
          ),
        ),
      );
      if (preview == controller) preview = null;
      controller.dispose();
    } catch (e) {
      if (mounted && allowed) setState(() => error = '$e');
    } finally {
      if (mounted && captured == epoch) setState(() => busy = false);
    }
  }

  Future<void> sourceDetails(String path, String title) async {
    if (!allowed) return;
    final captured = epoch;
    try {
      final item = businessMap(await widget.session.read(path));
      if (!mounted || captured != epoch || !allowed) return;
      final message = path.startsWith('/inventory/')
          ? 'Entnahme ${item['sequence_number']}\n${item['article_snapshot']?['name'] ?? origin?['article']?['name']}\nMenge: ${item['quantity']}\nErfasst: ${businessDate(item['created_at'], time: true)}'
          : 'Bestellung: ${item['confirmation']?['order_reference'] ?? origin?['order_reference']}\nLieferant: ${item['supplier_name']}\nStatus: ${item['status']}\n${businessItems(item['items']).map((row) => '${row['article_name']} · ${row['received_quantity']} / ${row['ordered_quantity']} ${row['unit']}').join('\n')}';
      await showDialog<void>(
        context: context,
        builder: (_) => _SourceDetail(
          session: widget.session,
          allowed: () => allowed,
          title: title,
          message: message,
        ),
      );
    } catch (e) {
      if (mounted && allowed) setState(() => error = '$e');
    }
  }

  Widget sourceCard(Map<String, dynamic> source) {
    final pending = widget.session.pending(commandKey(source));
    final available = !RegExp(r'^0*(?:\.0*)?$')
        .hasMatch('${source['available_quantity']}');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${source['article']['name']} · ${source['receipt_reference']}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              'Bestellung ${source['order_reference']} · Position ${(source['line_index'] as int) + 1}',
            ),
            Text(
              'Noch ungebunden: ${source['available_quantity']} ${source['article']['unit']}',
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                if (source['document_accessible'] == true)
                  OutlinedButton(
                    onPressed: busy ? null : () => original(source),
                    child: const Text('Original-Lieferschein öffnen'),
                  )
                else if (writable)
                  OutlinedButton(
                    onPressed: busy ? null : () => attach(source),
                    child: const Text('Original-Lieferschein zuordnen'),
                  ),
                if (writable &&
                    (pending ||
                        (source['document_accessible'] == true &&
                            available &&
                            businessItems(source['issues']).isNotEmpty)))
                  FilledButton(
                    onPressed: busy ? null : () => create(source),
                    child: Text(
                      pending
                          ? 'Unbestätigte Zuordnung wiederholen'
                          : widget.asset == null
                          ? 'Gerät aus Lieferung anlegen'
                          : 'Diesem Gerät zuordnen',
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget originView() {
    final value = origin;
    if (value == null)
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Notice(
            'Für dieses Gerät ist noch keine Lieferherkunft bestätigt.',
          ),
          if (writable)
            FilledButton(
              onPressed: () {
                setState(() => choosing = true);
                load();
              },
              child: const Text('Lieferherkunft auswählen'),
            ),
        ],
      );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '${widget.asset!['name']} · ${value['serial_number']}',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        Text('Bestellung ${value['order_reference']}'),
        Text(
          'Lieferschein ${value['receipt_reference']} · ${businessDate(value['received_on'])}',
        ),
        Text(
          'Lieferposition ${(value['line_index'] as int) + 1}: ${value['article']['name']}',
        ),
        Text(
          'Entnahme ${value['issue_sequence_number']} · zugeordnet ${value['quantity']} ${value['article']['unit']}',
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            FilledButton(
              onPressed: busy ? null : () => original(value),
              child: const Text('Original-Lieferschein öffnen'),
            ),
            OutlinedButton(
              onPressed: () => sourceDetails(
                '/purchasing/orders/${value['order_id']}',
                'Bestellung',
              ),
              child: const Text('Bestellung öffnen'),
            ),
            OutlinedButton(
              onPressed: () => sourceDetails(
                '/inventory/movements/${value['issue_movement_id']}',
                'Materialentnahme',
              ),
              child: const Text('Materialentnahme öffnen'),
            ),
          ],
        ),
        const SizedBox(height: 24),
        Text(
          'Wartung für dieses Gerät',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        if (history.isEmpty) const Text('Noch keine Wartung geplant.'),
        for (final visit in history)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('${visit['contract_snapshot']?['title'] ?? 'Wartung'}'),
            subtitle: Text(
              '${businessDate(visit['due_date'])} · ${visit['status']}',
            ),
            trailing: visit['status'] == 'completed'
                ? TextButton(
                    onPressed: () => Navigator.push<void>(
                      context,
                      MaterialPageRoute(
                        builder: (_) => BusinessOperationDocumentPage(
                          session: widget.session,
                          path: '/service-reports',
                          id: visit['report_id'],
                          fields: const [],
                        ),
                      ),
                    ),
                    child: const Text('Servicebericht'),
                  )
                : null,
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        widget.asset == null ? 'Lieferungen und Geräte' : 'Geräteherkunft',
      ),
    ),
    body: !allowed
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: BusinessEmpty(
              'Zugang nicht verfügbar',
              'Für diese Ansicht werden Dokument- und Lagerleserechte im Projekt benötigt.',
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              if (busy) const LinearProgressIndicator(),
              if (error != null) Notice(error!, error: true),
              const Notice(
                'Die tatsächliche Herkunft wird ausdrücklich bestätigt. Eine Zuordnung erzeugt keine zusätzliche Lagerbewegung und keine weiteren Kosten. Transferketten werden nicht automatisch zugeordnet.',
              ),
              const SizedBox(height: 16),
              if (widget.asset != null && !choosing)
                originView()
              else ...[
                if (sources.isEmpty && !busy)
                  const Text(
                    'Noch keine projektgebundenen Lieferpositionen vorhanden.',
                  ),
                for (final source in sources) sourceCard(source),
                Wrap(
                  spacing: 12,
                  children: [
                    if (offset > 0)
                      TextButton(
                        onPressed: busy
                            ? null
                            : () {
                                setState(
                                  () => offset = (offset - 25).clamp(0, 100000),
                                );
                                load();
                              },
                        child: const Text('Vorherige Lieferpositionen'),
                      ),
                    if (nextOffset != null)
                      TextButton(
                        onPressed: busy
                            ? null
                            : () {
                                setState(() => offset = nextOffset!);
                                load();
                              },
                        child: const Text('Weitere Lieferpositionen'),
                      ),
                  ],
                ),
              ],
            ],
          ),
  );
}

class _SourceDetail extends StatelessWidget {
  const _SourceDetail({
    required this.session,
    required this.allowed,
    required this.title,
    required this.message,
  });
  final BusinessSession session;
  final bool Function() allowed;
  final String title, message;
  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: session,
    builder: (context, _) => AlertDialog(
      title: Text(title),
      content: SingleChildScrollView(
        child: SelectableText(
          allowed() ? message : 'Die aktuelle Lesefreigabe fehlt.',
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Schließen'),
        ),
      ],
    ),
  );
}

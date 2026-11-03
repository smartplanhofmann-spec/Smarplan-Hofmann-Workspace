import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart'
    show exportMailAttachment, safeAttachmentFilename;
import 'offline_vault.dart' show offlineId;

String _hex(List<int> value) =>
    value.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
String _money(String input) {
  final value = businessDecimal(input);
  if (!RegExp(r'^-?\d+(?:\.\d{1,2})?$').hasMatch(value))
    throw const FormatException(
      'Bitte EUR-Beträge mit höchstens zwei Nachkommastellen angeben.',
    );
  final parts = value.replaceFirst('-', '').split('.');
  var cents =
      BigInt.parse(parts[0]) * BigInt.from(100) +
      BigInt.parse((parts.length == 2 ? parts[1] : '').padRight(2, '0'));
  if (value.startsWith('-')) cents = -cents;
  final abs = cents.abs();
  return '${cents.isNegative ? '-' : ''}${abs ~/ BigInt.from(100)}.${(abs % BigInt.from(100)).toString().padLeft(2, '0')}';
}

BigInt _minor(String value) => BigInt.parse(_money(value).replaceAll('.', ''));

void Function(dynamic) projectReceiptUploadValidator({
  required String phase,
  required Map<String, dynamic> expected,
  String? mediaId,
}) {
  final frozen = Map<String, dynamic>.from(jsonDecode(jsonEncode(expected)));
  return (dynamic value) {
    final result = businessMap(value);
    if (result['project_id'] != frozen['project_id'] ||
        result['sha256'] != frozen['sha256'] ||
        result['filename'] != frozen['filename'] ||
        result['media_type'] != frozen['media_type'] ||
        !RegExp(r'^[a-f0-9]{32}$').hasMatch('${result['id']}') ||
        (phase == 'media-complete' &&
            (result['id'] != mediaId || result['status'] != 'ready')) ||
        (phase != 'capture' && result['size'] != frozen['size'])) {
      throw const ApiException(
        0,
        'Die Bestätigung passt nicht zum unveränderten Belegoriginal. Derselbe Auftrag bleibt für die Wiederholung erhalten.',
      );
    }
  };
}

void Function(dynamic) projectReceiptReviewValidator({
  required String project,
  required String receipt,
  required String originalHash,
  required Map<String, dynamic> expected,
}) {
  final frozen = Map<String, dynamic>.from(jsonDecode(jsonEncode(expected)));
  return (dynamic value) {
    final result = businessMap(value);
    if (result['id'] != receipt ||
        result['project_id'] != project ||
        result['sha256'] != originalHash ||
        result['revision'] != frozen['revision'] + 1 ||
        [
          'vendor',
          'invoice_number',
          'issue_date',
          'net',
          'tax',
          'gross',
          'currency',
          'status',
          'note',
        ].any((field) => result[field] != frozen[field])) {
      throw const ApiException(
        0,
        'Die Bestätigung stimmt nicht mit der Belegprüfung überein. Der ursprüngliche Auftrag bleibt erhalten.',
      );
    }
  };
}

class _ReceiptUpload {
  _ReceiptUpload({
    required this.id,
    required this.bytes,
    required this.manifest,
  });
  final String id;
  final Uint8List bytes;
  final Map<String, dynamic> manifest;
  Map<String, dynamic>? media;
  int nextChunk = 0;
  bool complete = false, started = false, busy = false;
}

class _ReceiptUploads extends ChangeNotifier {
  _ReceiptUploads(this.session) {
    session.addListener(changed);
  }
  final BusinessSession session;
  final byProject = <String, _ReceiptUpload>{};
  void updated() => notifyListeners();
  void changed() {
    if (!session.allowed) byProject.clear();
    notifyListeners();
  }
}

final _uploadStores = Expando<_ReceiptUploads>();
_ReceiptUploads _uploads(BusinessSession session) =>
    _uploadStores[session] ??= _ReceiptUploads(session);

/// Receipt files stay in memory within the current authenticated session while
/// upload acknowledgements are unresolved. Pages may close without a new nonce.
class BusinessProjectReceiptsPage extends StatefulWidget {
  const BusinessProjectReceiptsPage({
    super.key,
    required this.session,
    this.initialReceiptId,
    this.pickFile,
  });
  final BusinessSession session;
  final String? initialReceiptId;
  final Future<XFile?> Function()? pickFile;
  @override
  State<BusinessProjectReceiptsPage> createState() =>
      _BusinessProjectReceiptsPageState();
}

class _BusinessProjectReceiptsPageState
    extends State<BusinessProjectReceiptsPage> {
  List<Map<String, dynamic>> records = [];
  final previews = <MailAttachmentPreviewController>[];
  bool loading = false, denied = false;
  int epoch = 0;
  Object? generation;
  String? error, success;
  String get project => widget.session.projectId!;
  bool get readable =>
      !denied &&
      widget.session.projectId != null &&
      widget.session.can('finance.read') &&
      widget.session.hasModule('finance');
  bool get writable =>
      readable &&
      widget.session.canWrite('finance.write') &&
      widget.session.sectionEnabled('finance');
  _ReceiptUpload? get upload => _uploads(widget.session).byProject[project];
  @override
  void initState() {
    super.initState();
    generation = widget.session.generation;
    widget.session.addListener(changed);
    _uploads(widget.session).addListener(uploadChanged);
    load();
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    _uploads(widget.session).removeListener(uploadChanged);
    for (final preview in previews) {
      preview.revoke();
    }
    super.dispose();
  }

  void uploadChanged() {
    if (mounted) setState(() {});
  }

  void changed() {
    if (!mounted) return;
    if (!readable || generation != widget.session.generation) {
      epoch++;
      records = [];
      loading = false;
      generation = widget.session.generation;
      for (final preview in previews) {
        preview.revoke();
      }
    }
    setState(() {});
  }

  Future<void> load() async {
    if (!readable) return;
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = businessItems(
        await widget.session.read(widget.session.query('/finance/receipts')),
      );
      if (result.any((row) => row['project_id'] != project))
        throw const ApiException(
          0,
          'Die Belegliste gehört nicht vollständig zu diesem Projekt.',
        );
      if (mounted && current == epoch && readable)
        setState(
          () => records = [
            ...result.where((r) => r['id'] == widget.initialReceiptId),
            ...result.where((r) => r['id'] != widget.initialReceiptId),
          ],
        );
    } on ApiException catch (e) {
      if (mounted && current == epoch) {
        if ([403, 404].contains(e.status)) {
          denied = true;
          records = [];
        }
        setState(() => error = '$e');
      }
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> choose() async {
    if (!writable || upload != null) return;
    final current = epoch;
    try {
      final file =
          await (widget.pickFile?.call() ??
              openFile(
                acceptedTypeGroups: [
                  const XTypeGroup(
                    label: 'Eingangsbeleg',
                    extensions: ['pdf', 'png', 'jpg', 'jpeg'],
                    uniformTypeIdentifiers: [
                      'com.adobe.pdf',
                      'public.png',
                      'public.jpeg',
                    ],
                  ),
                ],
              ));
      if (file == null || !mounted || current != epoch || !writable) return;
      const maximum = 20 * 1024 * 1024;
      final length = await file.length();
      if (length < 1 || length > maximum)
        throw const ApiException(
          413,
          'Bitte ein PDF-, JPEG- oder PNG-Original mit höchstens 20 MiB auswählen.',
        );
      final builder = BytesBuilder(copy: false);
      await for (final chunk in file.openRead()) {
        builder.add(chunk);
        if (builder.length > maximum)
          throw const ApiException(413, 'Das Original ist größer als 20 MiB.');
      }
      final bytes = builder.takeBytes();
      if (bytes.length != length)
        throw const ApiException(
          409,
          'Die Datei wurde während der Auswahl geändert. Bitte erneut auswählen.',
        );
      String? type;
      if (bytes.length >= 5 &&
          ascii.decode(bytes.sublist(0, 5), allowInvalid: true) == '%PDF-')
        type = 'application/pdf';
      if (bytes.length >= 8 &&
          base64Encode(bytes.sublist(0, 8)) == 'iVBORw0KGgo=')
        type = 'image/png';
      if (bytes.length >= 3 &&
          bytes[0] == 255 &&
          bytes[1] == 216 &&
          bytes[2] == 255)
        type = 'image/jpeg';
      if (type == null)
        throw const ApiException(
          415,
          'Hier sind PDF-, JPEG- und PNG-Originale möglich. Der Dateityp muss zum Inhalt passen.',
        );
      final hash = _hex((await Sha256().hash(bytes)).bytes);
      if (!mounted || current != epoch || !writable) return;
      _uploads(widget.session).byProject[project] = _ReceiptUpload(
        id: offlineId(),
        bytes: bytes,
        manifest: {
          'project_id': project,
          'filename': safeAttachmentFilename(file.name),
          'media_type': type,
          'size': bytes.length,
          'sha256': hash,
        },
      );
      setState(() {
        error = null;
        success = null;
      });
      await send();
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    }
  }

  Future<Map<String, dynamic>> operation(
    _ReceiptUpload item,
    String phase,
    String path,
    Map<String, dynamic> body,
  ) async {
    final key = 'project-receipt-$phase-$project-${item.id}';
    return businessMap(
      widget.session.pending(key)
          ? await widget.session.repeatProjectReceiptCommand(
              project,
              item.id,
              phase: phase,
            )
          : await widget.session.command(
              key,
              path,
              body,
              validateResult: projectReceiptUploadValidator(
                phase: phase,
                expected: item.manifest,
                mediaId: item.media?['id'],
              ),
            ),
    );
  }

  void requireUpload(_ReceiptUpload item) {
    if (!writable || _uploads(widget.session).byProject[project] != item)
      throw const ApiException(
        403,
        'Die Belegübertragung ist nicht mehr freigegeben.',
      );
  }

  Future<void> send() async {
    final item = upload;
    if (item == null || item.busy || !writable) return;
    item.busy = true;
    item.started = true;
    if (mounted)
      setState(() {
        error = null;
        success = null;
      });
    try {
      requireUpload(item);
      if (item.media == null) {
        final result = await operation(
          item,
          'media',
          '/receipt-media',
          item.manifest,
        );
        requireUpload(item);
        if (result['project_id'] != project ||
            result['sha256'] != item.manifest['sha256'] ||
            !RegExp(r'^[a-f0-9]{32}$').hasMatch('${result['id']}'))
          throw const ApiException(
            0,
            'Die Uploadbestätigung passt nicht zum Original.',
          );
        item.media = result;
      }
      final mediaId = item.media!['id'];
      if (!item.complete) {
        for (
          var index = item.nextChunk;
          index * 262144 < item.bytes.length;
          index++
        ) {
          requireUpload(item);
          final start = index * 262144,
              end = (start + 262144).clamp(0, item.bytes.length);
          await widget.session.api.call(
            widget.session.path('/receipt-media/$mediaId/chunks/$index'),
            {'content_base64': base64Encode(item.bytes.sublist(start, end))},
          );
          requireUpload(item);
          item.nextChunk = index + 1;
          if (mounted) setState(() {});
        }
        final completed = await operation(
          item,
          'media-complete',
          '/receipt-media/$mediaId/complete',
          {'project_id': project},
        );
        requireUpload(item);
        if (completed['id'] != mediaId ||
            completed['sha256'] != item.manifest['sha256'] ||
            completed['status'] != 'ready')
          throw const ApiException(
            0,
            'Das hochgeladene Original wurde noch nicht passend bestätigt.',
          );
        item.complete = true;
      }
      final received = await operation(item, 'capture', '/finance/receipts', {
        'project_id': project,
        'media_id': mediaId,
        'note': '',
      });
      requireUpload(item);
      if (received['project_id'] != project ||
          received['sha256'] != item.manifest['sha256'] ||
          received['filename'] != item.manifest['filename'] ||
          !RegExp(r'^[a-f0-9]{32}$').hasMatch('${received['id']}'))
        throw const ApiException(
          0,
          'Die Eingangsbestätigung stimmt nicht mit dem Belegoriginal überein.',
        );
      _uploads(widget.session).byProject.remove(project);
      if (mounted) {
        setState(
          () => success = 'Das Belegoriginal ist gesichert. Die Angaben müssen jetzt geprüft werden.',
        );
        await load();
      }
    } on ApiException catch (e) {
      if (e.status == 401) widget.session.revoke();
      if (mounted) {
        if ([403, 404].contains(e.status)) {
          denied = true;
          records = [];
          for (final preview in previews) {
            preview.revoke();
          }
        }
        setState(() => error = '$e');
      }
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      item.busy = false;
      _uploads(widget.session).updated();
      if (mounted) setState(() {});
    }
  }

  Future<void> original(Map<String, dynamic> row) async {
    final current = epoch;
    try {
      await widget.session.load();
      if (!mounted || current != epoch || !readable) return;
      final source = businessMap(
        await widget.session.read('/finance/receipts/${row['id']}'),
      );
      if (source['project_id'] != project || source['id'] != row['id'])
        throw const ApiException(
          0,
          'Der Beleg gehört nicht zu diesem Projekt.',
        );
      final bytes = await widget.session.api.bytes(
        widget.session.path('/finance/receipts/${row['id']}/original'),
        mediaType: source['media_type'],
      );
      final hash = _hex((await Sha256().hash(bytes)).bytes);
      if (!mounted || current != epoch || !readable) return;
      if (hash != source['sha256'])
        throw const ApiException(
          0,
          'Die Originaldatei stimmt nicht mit ihrer Prüfsumme überein.',
        );
      final controller = MailAttachmentPreviewController(
        VerifiedMailAttachment(
          bytes: bytes,
          filename: source['filename'],
          mediaType: source['media_type'],
          sha256: hash,
        ),
      );
      previews.add(controller);
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => MailAttachmentPreviewPage(
            controller: controller,
            mayView: () => readable,
            exporter: exportMailAttachment,
          ),
        ),
      );
      previews.remove(controller);
      controller.dispose();
    } on ApiException catch (e) {
      if (mounted && current == epoch) {
        if ([403, 404].contains(e.status)) {
          denied = true;
          records = [];
        }
        setState(() => error = '$e');
      }
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    }
  }

  Future<void> review(Map<String, dynamic> row) async {
    if (!writable || !widget.session.canWrite('finance.approve')) return;
    final key = 'project-receipt-review-$project-${row['id']}';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Eingangsbeleg prüfen',
        readPermission: 'finance.read',
        writePermission: 'finance.approve',
        pendingKey: key,
        initial: {
          ...row,
          'status': ['reviewed', 'rejected'].contains(row['status'])
              ? row['status']
              : '',
          'confirmed': false,
        },
        fields: const [
          BusinessField('vendor', 'Lieferant / Aussteller', required: true),
          BusinessField('invoice_number', 'Belegnummer', required: true),
          BusinessField(
            'issue_date',
            'Belegdatum',
            type: BusinessInput.date,
            required: true,
          ),
          BusinessField(
            'net',
            'Nettobetrag laut Beleg (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'tax',
            'Ausgewiesene Steuer laut Beleg (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'gross',
            'Bruttobetrag laut Beleg (€)',
            type: BusinessInput.decimal,
            required: true,
          ),
          BusinessField(
            'status',
            'Prüfergebnis',
            type: BusinessInput.choice,
            required: true,
            choices: {
              '': 'Bitte ausdrücklich wählen',
              'reviewed': 'Angaben geprüft',
              'rejected': 'Beleg abgelehnt',
            },
          ),
          BusinessField('note', 'Prüfnotiz', type: BusinessInput.multiline),
          BusinessField(
            'confirmed',
            'Ich habe Original und Beträge geprüft. Die Steuerangabe beschreibt nur den Beleg und entscheidet nicht über den Vorsteuerabzug.',
            type: BusinessInput.toggle,
            initial: false,
          ),
        ],
        saveLabel: 'Belegprüfung festhalten',
        readAllowed: () => readable,
        onSave: (values) async {
          if (!writable || !widget.session.canWrite('finance.approve'))
            throw const ApiException(
              403,
              'Die Belegprüfung ist nicht freigegeben.',
            );
          if (widget.session.pending(key)) {
            await widget.session.repeatProjectReceiptCommand(
              project,
              row['id'],
              review: true,
            );
            return;
          }
          if (values['confirmed'] != true)
            throw const FormatException(
              'Bitte die Prüfung des Belegoriginals ausdrücklich bestätigen.',
            );
          final net = _money('${values['net']}'),
              tax = _money('${values['tax']}'),
              gross = _money('${values['gross']}');
          if (_minor(net) + _minor(tax) != _minor(gross))
            throw const FormatException(
              'Nettobetrag und ausgewiesene Steuer müssen den Bruttobetrag ergeben.',
            );
          final request = <String, dynamic>{
            for (final field in [
              'vendor',
              'invoice_number',
              'issue_date',
              'status',
              'note',
            ])
              field: values[field],
            'net': net,
            'tax': tax,
            'gross': gross,
            'currency': 'EUR',
            'revision': row['revision'],
          };
          await widget.session.command(
            key,
            '/finance/receipts/${row['id']}',
            request,
            validateResult: projectReceiptReviewValidator(
              project: project,
              receipt: row['id'],
              originalHash: row['sha256'],
              expected: request,
            ),
          );
        },
      ),
    );
    if (mounted && readable) await load();
  }

  @override
  Widget build(BuildContext context) {
    final current = readable ? upload : null;
    return Scaffold(
      appBar: AppBar(title: const Text('Projekt-Eingangsbelege')),
      body: !readable
          ? const Padding(
              padding: EdgeInsets.all(24),
              child: BusinessEmpty(
                'Eingangsbelege nicht freigegeben',
                'Unbestätigte Übertragungen bleiben in dieser Sitzung erhalten. Mit aktuellen Rechten erneut öffnen.',
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(24),
              children: [
                const Notice(
                  'Das Original bleibt unverändert erhalten. Die Belegprüfung erfasst die ausgewiesenen EUR-Beträge; sie löst keine Zahlung aus und entscheidet nicht über den Vorsteuerabzug.',
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  children: [
                    FilledButton.icon(
                      onPressed: writable && current == null ? choose : null,
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Belegoriginal auswählen'),
                    ),
                    OutlinedButton(
                      onPressed: loading ? null : load,
                      child: const Text('Belegliste aktualisieren'),
                    ),
                  ],
                ),
                if (error != null) Notice(error!, error: true),
                if (success != null) Notice(success!),
                if (loading || current?.busy == true)
                  const LinearProgressIndicator(),
                if (current != null)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${current.manifest['filename']}',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const Text(
                            'Die Übertragung ist noch nicht vollständig bestätigt. Das ausgewählte Original und die ursprünglichen Aufträge bleiben für die Wiederholung in dieser Sitzung erhalten.',
                          ),
                          OutlinedButton(
                            onPressed: writable && !current.busy ? send : null,
                            child: const Text(
                              'Übertragung unverändert fortsetzen',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (records.isEmpty && !loading)
                  const BusinessEmpty(
                    'Noch keine Eingangsbelege',
                    'PDF-, JPEG- oder PNG-Original auswählen, danach Angaben prüfen.',
                  ),
                for (final row in records)
                  Card(
                    key: ValueKey('project-receipt-${row['id']}'),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${row['filename']}',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          if (row['vendor'] != null)
                            Text('${row['vendor']} · ${row['invoice_number']}'),
                          Text(
                            row['status'] == 'reviewed'
                                ? 'Geprüft · Fassung ${row['revision']}'
                                : row['status'] == 'rejected'
                                ? 'Abgelehnt · Fassung ${row['revision']}'
                                : 'Belegprüfung ausstehend',
                          ),
                          if (row['net'] != null)
                            Text(
                              'Netto ${businessMoney(row['net'])} · Steuer laut Beleg ${businessMoney(row['tax'])} · Brutto ${businessMoney(row['gross'])}',
                            ),
                          Wrap(
                            spacing: 8,
                            children: [
                              TextButton(
                                onPressed: () => original(row),
                                child: const Text('Original ansehen'),
                              ),
                              if (writable &&
                                  widget.session.canWrite('finance.approve'))
                                OutlinedButton(
                                  onPressed: () => review(row),
                                  child: Text(
                                    widget.session.pending(
                                          'project-receipt-review-$project-${row['id']}',
                                        )
                                        ? 'Unbestätigte Prüfung öffnen'
                                        : row['revision'] == 0
                                        ? 'Beleg prüfen'
                                        : 'Belegprüfung korrigieren',
                                  ),
                                ),
                            ],
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

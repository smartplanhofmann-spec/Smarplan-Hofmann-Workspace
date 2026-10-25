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
import 'mail_attachment_widgets.dart' show exportMailAttachment;
import 'offline_vault.dart' show offlineId;

class BusinessAdaptersPage extends StatefulWidget {
  const BusinessAdaptersPage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessAdaptersPage> createState() => _BusinessAdaptersPageState();
}

class _BusinessAdaptersPageState extends State<BusinessAdaptersPage> {
  List<Map<String, dynamic>> adapters = [], profiles = [], suppliers = [];
  String? error;
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!widget.session.can('settings.manage')) {
        adapters = [];
        profiles = [];
        suppliers = [];
      }
      setState(() {});
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    try {
      final data = businessMap(await widget.session.read('/adapters'));
      if (mounted && widget.session.can('settings.manage'))
        setState(() {
          adapters = businessItems(data);
          profiles = (data['profiles'] as List? ?? [])
              .map(businessMap)
              .toList();
          suppliers = (data['suppliers'] as List? ?? [])
              .map(businessMap)
              .toList();
        });
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> configure([Map<String, dynamic>? current]) async {
    final id = current?['id'];
    final key = 'adapter-${id ?? offlineId()}';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: id == null
            ? 'Import- / Exportprofil einrichten'
            : 'Profil bearbeiten',
        initial: current ?? {},
        fields: [
          const BusinessField('name', 'Bezeichnung', required: true),
          if (id == null)
            BusinessField(
              'profile',
              'Formatprofil',
              required: true,
              type: BusinessInput.choice,
              choices: {
                for (final p in profiles)
                  '${p['id']}':
                      '${p['label']}${p['supported'] == true ? '' : ' · noch nicht freigegeben'}',
              },
            ),
          BusinessField(
            'supplier',
            'Lieferantenherkunft (optional)',
            type: BusinessInput.choice,
            choices: {
              for (final p in suppliers)
                '${p['id']}': '${p['name']} · Verbindung ungeprüft',
            },
          ),
          const BusinessField(
            'enabled',
            'Lokales Profil aktivieren',
            type: BusinessInput.toggle,
            initial: false,
          ),
          const BusinessField(
            'secret_ref',
            'Geschützte Server-Konfigurationsreferenz (optional)',
            hint: 'SMARTPLAN_… · hier keinen Schlüssel eingeben',
          ),
        ],
        onSave: (values) async {
          await widget.session.command(
            key,
            '/adapters${id == null ? '' : '/$id'}',
            {...values, if (id != null) 'revision': current!['revision']},
          );
        },
      ),
    );
    if (mounted) await load();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.can('settings.manage'))
      return const Scaffold(body: Center(child: Text('Kein Zugriff.')));
    return Scaffold(
      appBar: AppBar(title: const Text('Schnittstellenprofile')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Notice(
            'Lokale Import- und Prüfprofile sind keine bestätigten Liveverbindungen. Bestehender Gmail-Empfang und die Bot-Verbindungen bleiben unabhängig davon erhalten.',
          ),
          if (error != null) Notice(error!, error: true),
          if (widget.session.canWrite('settings.manage'))
            FilledButton.icon(
              onPressed: () => configure(),
              icon: const Icon(Icons.add),
              label: const Text('Profil einrichten'),
            ),
          const SizedBox(height: 20),
          for (final adapter in adapters)
            Card(
              child: ListTile(
                title: Text('${adapter['name']}'),
                subtitle: Text(
                  '${adapter['profile_info']?['label'] ?? adapter['profile']} · ${adapter['enabled'] == true ? 'Lokal aktiviert' : 'Deaktiviert'}\nKeine produktive Verbindung bestätigt',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () async {
                  await Navigator.push<void>(
                    context,
                    MaterialPageRoute(
                      builder: (_) => BusinessAdapterPage(
                        session: widget.session,
                        adapter: adapter,
                        onConfigure: () => configure(adapter),
                      ),
                    ),
                  );
                  if (mounted) await load();
                },
              ),
            ),
          const SizedBox(height: 20),
          Text(
            'Unterstützungsumfang',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          for (final profile in profiles)
            Card(
              child: ListTile(
                title: Text('${profile['label']}'),
                subtitle: Text('${profile['scope']}'),
                leading: Icon(
                  profile['supported'] == true
                      ? Icons.rule_outlined
                      : Icons.lock_outline,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class BusinessAdapterPage extends StatefulWidget {
  const BusinessAdapterPage({
    super.key,
    required this.session,
    required this.adapter,
    required this.onConfigure,
  });
  final BusinessSession session;
  final Map<String, dynamic> adapter;
  final Future<void> Function() onConfigure;
  @override
  State<BusinessAdapterPage> createState() => _BusinessAdapterPageState();
}

class _BusinessAdapterPageState extends State<BusinessAdapterPage> {
  Map<String, dynamic>? staged;
  Map<String, dynamic>? pendingImport;
  String? error, notice;
  bool busy = false;
  late Map<String, dynamic> adapter;
  @override
  void initState() {
    super.initState();
    adapter = businessMap(widget.adapter);
    widget.session.addListener(changed);
  }

  void changed() {
    if (mounted) {
      if (!widget.session.can('settings.manage')) {
        staged = null;
        pendingImport = null;
      }
      if (!widget.session.can('finance.read')) {
        staged = null;
        pendingImport = null;
      }
      setState(() {});
    }
  }

  @override
  void dispose() {
    widget.session.removeListener(changed);
    pendingImport = null;
    staged = null;
    super.dispose();
  }

  bool get writable => widget.session.canWrite('settings.manage') && !busy;
  Map<String, dynamic> get profile => businessMap(adapter['profile_info']);
  Future<void> importFile() async {
    if (!widget.session.canWrite('finance.write') || busy) return;
    setState(() => busy = true);
    try {
      if (pendingImport == null) {
        final file = await openFile(
          acceptedTypeGroups: [
            const XTypeGroup(
              label: 'Importdatei',
              extensions: ['csv', 'txt', 'dat', 'xml', 'x83', 'datanorm'],
            ),
          ],
        );
        if (file == null) return;
        const limit = 2 * 1024 * 1024;
        if (await file.length() > limit)
          throw const ApiException(
            413,
            'Für dieses Prüfprofil sind höchstens 2 MiB zulässig.',
          );
        final builder = BytesBuilder(copy: false);
        await for (final part in file.openRead(0, limit + 1)) {
          builder.add(part);
          if (builder.length > limit)
            throw const ApiException(413, 'Die Datei überschreitet 2 MiB.');
        }
        if (!mounted || !widget.session.canWrite('finance.write')) return;
        pendingImport = {'content_base64': base64Encode(builder.takeBytes())};
      }
      final result = businessMap(
        await widget.session.command(
          'adapter-import-${adapter['id']}',
          '/adapters/${adapter['id']}/import',
          pendingImport!,
        ),
      );
      if (mounted && widget.session.can('settings.manage'))
        setState(() {
          staged = result;
          pendingImport = null;
          notice = 'Datei zur Prüfung eingelesen. Artikel wurden noch nicht geändert.';
        });
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> apply() async {
    final run = staged;
    if (run == null || !widget.session.canWrite('finance.write')) return;
    final datanorm = run['profile'] == 'datanorm_a14_cp850_v1';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Geprüfte Artikel übernehmen',
        fields: [
          const BusinessField(
            'confirmed',
            'Ich habe Herkunft, Positionen und Preise geprüft',
            type: BusinessInput.toggle,
          ),
          if (datanorm) ...[
            const BusinessField(
              'price_scale',
              'Rohpreis-Skalierung',
              type: BusinessInput.decimal,
              required: true,
              initial: '0.01',
              hint: 'Zum Beispiel 0,01 für Cent-Rohpreise',
            ),
            const BusinessField(
              'target_price',
              'Nettopreis zuordnen',
              type: BusinessInput.choice,
              required: true,
              choices: {
                'purchase_net': 'Einkaufspreis',
                'sales_net': 'Verkaufspreis',
              },
            ),
            const BusinessField(
              'tax_rate',
              'Umsatzsteuer (%)',
              type: BusinessInput.decimal,
              required: true,
              initial: '19',
            ),
          ],
        ],
        onSave: (values) async {
          if (values['confirmed'] != true)
            throw const FormatException(
              'Bitte die fachliche Prüfung ausdrücklich bestätigen.',
            );
          final result = businessMap(
            await widget.session.command(
              'adapter-apply-${run['id']}',
              '/adapters/imports/${run['id']}/apply',
              values,
            ),
          );
          if (mounted) setState(() => staged = result);
        },
      ),
    );
  }

  Future<void> saveArtifact(Map<String, dynamic> result) async {
    final bytes = base64Decode(result['artifact_base64']);
    if (bytes.length > 2 * 1024 * 1024)
      throw const ApiException(413, 'Die Prüfdatei ist zu groß.');
    final digest = (await Sha256().hash(bytes)).bytes
        .map((v) => v.toRadixString(16).padLeft(2, '0'))
        .join();
    if (digest != result['sha256'])
      throw const ApiException(
        0,
        'Prüfdatei und Prüfsumme stimmen nicht überein.',
      );
    if (!mounted || !widget.session.can('settings.manage')) return;
    await exportMailAttachment(
      context,
      VerifiedMailAttachment(
        bytes: bytes,
        filename: result['filename'],
        mediaType: result['media_type'],
        sha256: digest,
      ),
      () =>
          mounted &&
          widget.session.can('settings.manage') &&
          widget.session.can('finance.read'),
    );
  }

  Future<void> export() async {
    if (busy || !widget.session.can('finance.read')) return;
    final kind = adapter['profile'];
    final values = <String, dynamic>{};
    if (kind == 'gaeb_x83_inspect_v1') {
      if (staged == null) {
        setState(
          () => error = 'Zuerst eine GAEB-Datei prüfen, dann genau diese Positionen exportieren.',
        );
        return;
      }
      values['import_id'] = staged!['id'];
    } else if (kind != 'catalog_csv_v1') {
      final docs = businessItems(await widget.session.read('/documents'))
          .where(
            (d) =>
                d['status'] == 'final' &&
                [
                  'invoice',
                  'advance_invoice',
                  'cumulative_invoice',
                  'final_invoice',
                  'credit_note',
                ].contains(d['kind']),
          )
          .toList();
      if (!mounted) return;
      String? chosen;
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: widget.session,
          title: 'Beleg bewusst auswählen',
          fields: [
            BusinessField(
              'document_id',
              'Finaler Beleg',
              type: BusinessInput.choice,
              required: true,
              choices: {
                for (final d in docs)
                  '${d['id']}': '${d['number']} · ${d['buyer']?['name']}',
              },
            ),
          ],
          onSave: (selection) async {
            chosen = selection['document_id'];
          },
        ),
      );
      if (!mounted || chosen == null) return;
      final doc = docs.firstWhere((d) => d['id'] == chosen);
      final rates = (businessMap(doc['totals'])['tax_breakdown'] as List? ?? [])
          .map((row) => '${row['rate']}')
          .toSet();
      Map<String, dynamic>? mapping;
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: widget.session,
          title: 'Übergabemapping prüfen',
          fields: kind == 'lexware_review_json_v1'
              ? const [
                  BusinessField(
                    'remote_contact_id',
                    'Bestätigte Lexware-Kontakt-ID',
                    required: true,
                  ),
                ]
              : [
                  const BusinessField('account', 'Konto', required: true),
                  const BusinessField(
                    'contra_account',
                    'Gegenkonto',
                    required: true,
                  ),
                  for (final rate in rates)
                    BusinessField(
                      'tax_$rate',
                      'Steuerschlüssel für $rate %',
                      required: true,
                    ),
                ],
          onSave: (fields) async {
            mapping = kind == 'lexware_review_json_v1'
                ? fields
                : {
                    'account': fields['account'],
                    'contra_account': fields['contra_account'],
                    'tax_keys': {
                      for (final rate in rates) rate: fields['tax_$rate'],
                    },
                  };
          },
        ),
      );
      if (!mounted || mapping == null) return;
      values.addAll({
        'document_ids': [chosen],
        'mapping': {chosen!: mapping},
      });
    }
    setState(() => busy = true);
    try {
      final response = businessMap(
        await widget.session.command(
          'adapter-export-${adapter['id']}',
          '/adapters/${adapter['id']}/export',
          values,
        ),
      );
      final artifact = businessMap(response['result']);
      if (!mounted) return;
      setState(
        () => notice = 'Prüfdatei erzeugt. Keine DATEV-, Lexware- oder GAEB-Importabnahme und keine externe Zustellung zugesagt.',
      );
      await saveArtifact(artifact);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.session.can('settings.manage'))
      return const Scaffold(body: Center(child: Text('Kein Zugriff.')));
    final run = staged;
    return Scaffold(
      appBar: AppBar(title: Text('${adapter['name']}')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text(
            '${profile['label'] ?? adapter['profile']}',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 12),
          Notice('${profile['scope'] ?? ''}'),
          const Text(
            'Eine Liveverbindung oder Anbieterfreigabe ist nicht bestätigt.',
          ),
          if (error != null) Notice(error!, error: true),
          if (notice != null) Notice(notice!),
          if (busy) const LinearProgressIndicator(),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              if (widget.session.canWrite('settings.manage'))
                OutlinedButton(
                  onPressed: busy
                      ? null
                      : () async {
                          await widget.onConfigure();
                          final fresh = businessMap(
                            await widget.session.read(
                              '/adapters/${adapter['id']}',
                            ),
                          );
                          if (mounted && widget.session.allowed)
                            setState(() => adapter = fresh);
                        },
                  child: const Text('Profil bearbeiten'),
                ),
              if (adapter['enabled'] == true &&
                  profile['import'] == true &&
                  adapter['profile'] != 'website_lead_v1' &&
                  widget.session.canWrite('finance.write'))
                FilledButton(
                  onPressed: busy ? null : importFile,
                  child: Text(
                    pendingImport == null
                        ? 'Datei zur Prüfung einlesen'
                        : 'Dieselbe Datei erneut einlesen',
                  ),
                ),
              if (adapter['enabled'] == true &&
                  profile['export'] == true &&
                  widget.session.can('finance.read'))
                OutlinedButton(
                  onPressed: busy || widget.session.readonly ? null : export,
                  child: const Text('Prüfexport erstellen'),
                ),
            ],
          ),
          if (run != null) ...[
            const SizedBox(height: 24),
            Text(
              '${(run['rows'] as List? ?? []).length} eingelesene Positionen',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(
              run['status'] == 'applied'
                  ? 'Bestätigte Artikelübernahme abgeschlossen.'
                  : 'Noch nicht in den Artikelstamm übernommen.',
            ),
            for (final row
                in (run['rows'] as List? ?? []).take(50).map(businessMap))
              Card(
                child: ListTile(
                  title: Text('${row['code'] ?? ''} ${row['name'] ?? ''}'),
                  subtitle: Text(
                    '${row['unit'] ?? ''} · ${row['quantity'] ?? row['source_price_integer'] ?? row['cost_price_net'] ?? ''}',
                  ),
                ),
              ),
            if (run['status'] == 'staged' &&
                [
                  'catalog_csv_v1',
                  'datanorm_a14_cp850_v1',
                ].contains(run['profile']) &&
                widget.session.canWrite('finance.write'))
              FilledButton(
                onPressed: busy ? null : apply,
                child: const Text('Geprüfte Artikel übernehmen'),
              ),
          ],
        ],
      ),
    );
  }
}

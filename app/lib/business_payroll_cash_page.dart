import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:cryptography/cryptography.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'business_payroll_cash.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;
import 'mail_attachment_widgets.dart';

Map<String, dynamic> _copy(dynamic value) =>
    businessMap(jsonDecode(jsonEncode(value)));
String _ref(Map<String, dynamic> source) =>
    '${source['source_kind'] ?? source['kind']}:${source['id']}';
String _money(dynamic amount) => amount is int
    ? businessMoney(
        '${amount < 0 ? '-' : ''}${amount.abs() ~/ 100}.${(amount.abs() % 100).toString().padLeft(2, '0')}',
      )
    : 'Nicht belegt';

class BusinessPayrollCashPage extends StatefulWidget {
  const BusinessPayrollCashPage({
    super.key,
    required this.session,
    required this.employee,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  @override
  State<BusinessPayrollCashPage> createState() =>
      _BusinessPayrollCashPageState();
}

class _BusinessPayrollCashPageState extends State<BusinessPayrollCashPage> {
  BusinessSession get session => widget.session;
  String get employee => '${widget.employee['id']}';
  String get pendingKey => 'payroll-cash-$employee';
  Map<String, dynamic>? state, sources, preview, body;
  String? error;
  bool busy = false, accepted = false;
  Object? generation;
  bool get readable => payrollCashReadable(session);
  bool get writable =>
      payrollCashWritable(session) && state?['writes_allowed'] == true;
  @override
  void initState() {
    super.initState();
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    session.removeListener(changed);
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!readable || generation != null && generation != session.generation) {
        state = sources = preview = body = null;
        accepted = false;
      }
    });
  }

  Future<({Map<String, dynamic> state, Map<String, dynamic> sources})> fresh({
    bool write = false,
    String? instance,
  }) async {
    await session.load();
    if (!readable || write && !payrollCashWritable(session))
      throw const ApiException(
        403,
        'Aktuelle globale Personal-, Buchführungs- und Finanzrechte fehlen.',
      );
    final current = businessMap(await session.read('/payroll/cash'));
    if (!RegExp(r'^[a-f0-9]{32}$').hasMatch('${current['instance_id']}') ||
        current['batches'] is! List ||
        current['writes_allowed'] is! bool ||
        instance != null && instance != current['instance_id'])
      throw const ApiException(
        409,
        'Die Lohnzahlungsübernahme gehört nicht zur gebundenen Unternehmensinstanz.',
      );
    if (write && current['writes_allowed'] != true)
      throw const ApiException(
        423,
        'Die Lohnzahlungsübernahme ist aktuell gesperrt.',
      );
    final page = businessMap(
      await session.read('/payroll/cash/sources?employee_id=$employee'),
    );
    if (page['employee_id'] != employee ||
        page['instance_id'] != current['instance_id'] ||
        [
          'net_sources',
          'remittance_sources',
          'evidence_files',
        ].any((k) => page[k] is! List))
      throw const ApiException(
        0,
        'Die privaten Zahlungsquellen gehören nicht zur ausgewählten Person.',
      );
    if (!readable || write && !payrollCashWritable(session))
      throw const ApiException(
        403,
        'Die privaten Personal- und Finanzrechte wurden während des Vorgangs geändert.',
      );
    generation = session.generation;
    return (state: current, sources: page);
  }

  void failure(Object e) {
    if (mounted) setState(() => error = '$e');
  }

  Future<void> load() async {
    try {
      final access = await fresh();
      if (mounted && readable)
        setState(() {
          state = access.state;
          sources = access.sources;
          error = null;
        });
    } catch (e) {
      failure(e);
    }
  }

  Future<void> action(Future<void> Function() fn) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await fn();
    } catch (e) {
      failure(e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> present(Future<void> Function() fn) async {
    try {
      await fn();
    } catch (e) {
      failure(e);
    }
  }

  Widget card(String title, List<Widget> content) => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 10),
          ...content,
        ],
      ),
    ),
  );
  Widget projection(Map<String, dynamic> source) {
    payrollCashPublic(source);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Notice(
          source['status'] == 'void'
              ? 'Nachweisaufhebung, keine tatsächliche Rückzahlung. Eine vorhandene EÜR-Einordnung ausdrücklich berichtigen.'
              : 'Öffentliche Finanzsicht ohne Beschäftigten-/Originaldaten. Keine Überweisung oder amtliche Meldung.',
        ),
        for (final m in source['cash_movements'])
          ListTile(
            title: Text(
              '${businessDate(m['date'])} · ${m['direction'] == 'in' ? 'Arbeitnehmerzahlung / Zufluss' : 'Abfluss'} ${businessMoney(m['amount'])}',
            ),
            subtitle: Text(
              '${m['account']['code']} · ${m['account']['name']}\n${businessMap(m['categories']).entries.map((e) => '${payrollCashCategories[e.key]}: ${businessMoney(e.value)}').join('\n')}',
            ),
          ),
      ],
    );
  }

  Future<void> edit(
    String kind, {
    Map<String, dynamic>? previous,
    String mode = 'adopt',
  }) async {
    final access = await fresh(write: true),
        batchId = previous?['id'] ?? offlineId(),
        list = businessItems(
          access.sources[kind == 'net' ? 'net_sources' : 'remittance_sources'],
        ).where((s) => s['eligible'] == true).toList(),
        chosen = businessItems(previous?['command']?['sources'] ?? []),
        ids = chosen.map((s) => s['account_record_id'] ?? s['id']).toSet();
    if (session.pending(pendingKey)) return;
    if (mode == 'void') {
      await details(
        kind,
        [],
        access.state,
        access.sources,
        batchId,
        previous,
        mode,
      );
      return;
    }
    if (!mounted) return;
    List<Map<String, dynamic>>? selected;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Belegte Lohnzahlungsquellen auswählen',
        readAllowed: () => readable && session.generation == generation,
        fields: [
          BusinessField(
            'source_refs',
            'Vollständige Quellen dieser Person',
            type: BusinessInput.multiple,
            required: true,
            initial: list
                .where((s) => ids.contains(s['id']))
                .map(_ref)
                .toList(),
            choices: {
              for (final s in list)
                _ref(
                  s,
                ): '${s['month']} · ${s['kind'] ?? s['source_kind']} · Fassung ${s['revision']}',
            },
          ),
        ],
        saveLabel: 'Zahlungsteile ausdrücklich auswählen',
        onSave: (values) async {
          selected = list
              .where(
                (s) => (values['source_refs'] as List? ?? []).contains(_ref(s)),
              )
              .toList();
          if (selected!.isEmpty)
            throw const FormatException(
              'Mindestens eine vollständige belegte Quelle auswählen.',
            );
        },
      ),
    );
    if (selected != null && mounted)
      await details(
        kind,
        selected!,
        access.state,
        access.sources,
        batchId,
        previous,
        mode,
      );
  }

  Future<void> details(
    String kind,
    List<Map<String, dynamic>> selected,
    Map<String, dynamic> initial,
    Map<String, dynamic> initialSources,
    String batchId,
    Map<String, dynamic>? previous,
    String mode,
  ) async {
    final banks = businessItems(await session.read('/accounting/accounts')),
        chosen = businessItems(previous?['command']?['sources'] ?? []),
        files = businessItems(initialSources['evidence_files'])
            .where((f) => f['employee_id'] == employee)
            .toList();
    final fields = <BusinessField>[
      if (mode != 'void')
        BusinessField(
          'account_id',
          'Tatsächlich verwendetes Geldkonto',
          type: BusinessInput.choice,
          required: true,
          initial: previous?['command']?['account_id'] ?? '',
          choices: {
            '': 'Geldkonto ausdrücklich auswählen',
            for (final bank in banks.where((b) => b['active'] == true))
              '${bank['id']}': '${bank['code']} · ${bank['name']}',
          },
        ),
    ];
    for (var index = 0; index < selected.length; index++) {
      final s = selected[index];
      if (kind == 'net') {
        final saved = chosen
            .where(
              (v) =>
                  v['account_record_id'] == s['id'] &&
                  v['revision'] == s['revision'] &&
                  v['content_hash'] == s['content_hash'],
            )
            .firstOrNull;
        fields.add(
          BusinessField(
            'parts_$index',
            '${s['month']}: ausdrücklich zu übernehmende tatsächliche Zahlungsteile',
            type: BusinessInput.multiple,
            initial: (saved?['payment_indexes'] as List? ?? [])
                .map((i) => '$i')
                .toList(),
            choices: {
              for (final p in businessItems(s['payments']).where(
                (p) =>
                    p['already_imported'] != true ||
                    p['import_batch_id'] == previous?['id'],
              ))
                '${p['index']}':
                    '${businessDate(p['paid_on'])} · ${_money(p['amount_minor'])} · ${p['amount_minor'] < 0 ? 'Arbeitnehmerzahlung · ' : ''}${p['payment_reference']}',
            },
          ),
        );
      } else {
        for (final e in payrollRemittance.entries)
          fields.add(
            BusinessField(
              'remit_${index}_${e.key}',
              '${s['month']}: ${e.value}',
              type: BusinessInput.decimal,
              required: true,
              hint:
                  'Berechnete Obergrenze ${_money(s['calculated'][e.key])}; noch nicht übernommen ${_money(s['remaining'][e.key])}. Tatsächlich gezahlten Betrag ausdrücklich eingeben, auch bekannte 0.',
            ),
          );
      }
    }
    final fileOptions = {
      '': 'Geschütztes Original auswählen',
      for (final f in files) '${f['id']}': '${f['filename']}',
    };
    if (kind == 'remittance' && mode != 'void')
      fields.addAll([
        const BusinessField(
          'paid_on',
          'Tatsächlicher Abführungstag',
          type: BusinessInput.date,
          required: true,
        ),
        const BusinessField(
          'payment_reference',
          'Eindeutige Zahlungsreferenz',
          required: true,
        ),
        const BusinessField(
          'amount_minor',
          'Vollständiger tatsächlich bezahlter Betrag (€)',
          type: BusinessInput.decimal,
          required: true,
        ),
        BusinessField(
          'source_file_id',
          'Privates Original der tatsächlichen Abführung',
          type: BusinessInput.choice,
          required: true,
          choices: fileOptions,
        ),
      ]);
    if (mode != 'adopt')
      fields.add(
        BusinessField(
          'correction_file_id',
          'Privates Original der Nachweiskorrektur',
          type: BusinessInput.choice,
          required: true,
          choices: fileOptions,
        ),
      );
    fields.add(
      BusinessField(
        'reason',
        mode == 'adopt' ? 'Übernahmegrund' : 'Nachweiskorrekturgrund',
        type: BusinessInput.multiline,
        required: true,
      ),
    );
    if (!mounted) return;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: mode == 'void'
            ? 'Fälschlichen Zahlungsnachweis aufheben'
            : kind == 'net'
            ? 'Tatsächliche Nettozahlungen auswählen'
            : 'Tatsächliche Abführungen belegen',
        readAllowed: () => readable && session.generation == generation,
        fields: fields,
        saveLabel: 'Übernahme unverbindlich prüfen',
        onSave: (values) async {
          final current = await fresh(
            write: true,
            instance: initial['instance_id'],
          );
          if (session.pending(pendingKey))
            throw const ApiException(
              409,
              'Zuerst die offene Lohnzahlungsübernahme unverändert klären.',
            );
          final input = payrollCashInput(
                employee,
                current.state,
                current.sources,
                banks,
                values,
                kind: kind,
                batchId: batchId,
                selected: selected,
                previous: previous,
                action: mode,
              ),
              proof = payrollCashPreview(
                await session.api.call(
                  session.path('/payroll/cash/preview'),
                  input,
                ),
                input,
              );
          if (mounted && readable)
            setState(() {
              preview = proof;
              body = {
                ...input,
                'preview_hash': proof['preview_hash'],
                'confirmation': true,
              };
              accepted = false;
              error = null;
            });
        },
      ),
    );
  }

  Future<void> confirm() async {
    if (!accepted || body == null || preview == null) return;
    final input = _copy(body), proof = _copy(preview);
    await fresh(write: true, instance: input['instance_id']);
    if (session.pending(pendingKey)) {
      await session.repeatPayrollCashCommand(employee);
    } else {
      await session.command(
        pendingKey,
        '/payroll/cash/batches',
        input,
        validateResult: payrollCashValidator(input, proof),
      );
    }
    if (mounted)
      setState(() {
        body = preview = null;
        accepted = false;
      });
    await load();
  }

  Future<void> retry() async {
    await session.repeatPayrollCashCommand(employee);
    if (mounted)
      setState(() {
        body = preview = null;
        accepted = false;
      });
    await load();
  }

  Future<void> original(Map<String, dynamic> reference) async {
    await fresh();
    final opening = session.generation;
    final page = businessItems(
      await session.read('/personnel/files?employee_id=$employee'),
    );
    final file = page
        .where(
          (f) =>
              f['id'] == reference['id'] &&
              f['employee_id'] == employee &&
              f['purpose'] == 'personnel' &&
              f['sha256'] == reference['sha256'],
        )
        .firstOrNull;
    if (file == null)
      throw const ApiException(
        403,
        'Dieses private Original ist für die gewählte Person nicht freigegeben.',
      );
    final bytes = await session.api.bytes(
          session.path('/personnel/files/${file['id']}/content'),
          mediaType: file['media_type'],
        ),
        hash = (await Sha256().hash(bytes)).bytes
            .map((v) => v.toRadixString(16).padLeft(2, '0'))
            .join();
    if (bytes.length != file['size'] || hash != file['sha256'])
      throw const ApiException(
        0,
        'Das private Original stimmt nicht mit seinem Nachweis überein.',
      );
    await fresh();
    if (!mounted || !readable || opening != session.generation) return;
    await exportMailAttachment(
      context,
      VerifiedMailAttachment(
        bytes: bytes,
        filename: file['filename'],
        mediaType: file['media_type'],
        sha256: hash,
      ),
      () => mounted && readable && opening == session.generation,
    );
  }

  Future<void> detail(Map<String, dynamic> meta, {int? revision}) async {
    final access = await fresh(),
        result = businessMap(
          await session.read(
            '/payroll/cash/batches/${meta['id']}${revision == null ? '' : '?revision=$revision'}',
          ),
        );
    if (result['id'] != meta['id'] ||
        result['instance_id'] != access.state['instance_id'] ||
        result['command'] is! Map ||
        revision != null && result['revision'] != revision)
      throw const ApiException(
        0,
        'Der private Übernahmenachweis konnte nicht gebunden werden.',
      );
    final refs = <String, Map<String, dynamic>>{};
    for (final raw in [
      ...businessItems(result['source_records']).map((s) => s['source_file']),
      result['correction_file'],
      ...businessItems(access.sources['evidence_files']).where(
        (f) => f['id'] == result['command']['settlement']?['source_file_id'],
      ),
    ]) {
      final file = businessMap(raw);
      if (file['employee_id'] == employee) refs['${file['id']}'] = file;
    }
    final personBound =
        businessItems(result['source_records']).isNotEmpty &&
        businessItems(result['source_records'])
            .every((s) => s['record']?['employee_id'] == employee);
    final opening = session.generation;
    String? next;
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (_) => AnimatedBuilder(
        animation: session,
        builder: (context, _) => !readable || session.generation != opening
            ? AlertDialog(
                title: const Text('Zugang geändert'),
                content: const Notice(
                  'Private Zahlungsnachweise sind nicht mehr freigegeben.',
                  error: true,
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Schließen'),
                  ),
                ],
              )
            : AlertDialog(
                title: Text(
                  revision == null
                      ? 'Privater Lohnzahlungsnachweis'
                      : 'Historischer Lohnzahlungsnachweis',
                ),
                content: SizedBox(
                  width: 650,
                  child: SingleChildScrollView(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        projection(businessMap(result['public_source'])),
                        Text(
                          'Fassung ${result['revision']} · ${result['command']['reason']}',
                        ),
                        const Notice(
                          'Private Zahlungsquellen. Historische Fassungen bleiben erhalten.',
                        ),
                        for (final source in businessItems(
                          result['source_records'],
                        ))
                          ListTile(
                            title: Text(
                              '${source['month']} · ${source['record']?['kind'] ?? 'Laufnachweis'}',
                            ),
                            subtitle: Text(
                              'Fassung ${source['record']?['revision']} · ${source['source_file']?['filename'] ?? 'Geschütztes Original'}',
                            ),
                          ),
                        for (final file in refs.values)
                          TextButton(
                            onPressed: () => present(() => original(file)),
                            child: Text(
                              'Geschütztes Original: ${file['filename']}',
                            ),
                          ),
                        if (revision == null)
                          for (var i = 1; i <= result['revision']; i++)
                            TextButton(
                              onPressed: () {
                                next = 'revision:$i';
                                Navigator.pop(context);
                              },
                              child: Text('Historische Fassung $i'),
                            ),
                        if (revision == null &&
                            writable &&
                            personBound &&
                            !session.pending(pendingKey))
                          ...['replace', 'void'].map(
                            (mode) => TextButton(
                              onPressed: () {
                                next = mode;
                                Navigator.pop(context);
                              },
                              child: Text(
                                mode == 'replace'
                                    ? 'Zahlungsnachweis korrigieren'
                                    : 'Fälschlichen Nachweis aufheben',
                              ),
                            ),
                          ),
                        if (!personBound)
                          const Notice(
                            'Korrekturen dieser Übernahme in der Ansicht der betroffenen Person öffnen; gemischte Personalquellen separat prüfen.',
                          ),
                      ],
                    ),
                  ),
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Schließen'),
                  ),
                ],
              ),
      ),
    );
    if (next == null || !mounted) return;
    if (next!.startsWith('revision:')) {
      await detail(meta, revision: int.parse(next!.split(':').last));
    } else {
      await edit(result['kind'], previous: result, mode: next!);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = state, p = sources;
    return Scaffold(
      appBar: AppBar(
        title: Text('Belegte Lohnzahlungen · ${widget.employee['name']}'),
        actions: [
          IconButton(
            onPressed: busy ? null : load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Neu prüfen',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Notice(
            'Nur tatsächliche belegte Nettozahlungen und gesondert belegte Abführungen 2026. Keine Überweisung und keine automatische EÜR-Buchung. Die öffentliche Finanzquelle danach unter EÜR ausdrücklich einordnen.',
          ),
          if (error != null) Notice(error!, error: true),
          if (busy) const LinearProgressIndicator(),
          if (!readable)
            const Notice(
              'Die privaten Personal- und Finanzrechte fehlen.',
              error: true,
            )
          else if (s == null || p == null)
            const LinearProgressIndicator()
          else ...[
            if (session.pending(pendingKey))
              card('Unbestätigte Übernahme', [
                const Text(
                  'Originalbody und Vorgangskennung bleiben in dieser Sitzung erhalten.',
                ),
                FilledButton(
                  onPressed: busy || !writable ? null : () => action(retry),
                  child: const Text(
                    'Ursprüngliche Lohnzahlungsübernahme erneut senden',
                  ),
                ),
              ]),
            if (preview != null && !session.pending(pendingKey))
              card('Geprüfte Lohnzahlungsübernahme', [
                projection(businessMap(preview!['public_source'])),
                for (final warning in preview!['warnings'])
                  Notice(warning is String ? warning : '${warning['message']}'),
                CheckboxListTile(
                  value: accepted,
                  onChanged: busy
                      ? null
                      : (v) => setState(() => accepted = v == true),
                  title: const Text(
                    'Ich bestätige ausschließlich die nachgewiesenen tatsächlichen Zahlungen und das gewählte Geldkonto.',
                  ),
                ),
                FilledButton(
                  onPressed: accepted && writable && !busy
                      ? () => action(confirm)
                      : null,
                  child: const Text('Zahlungsnachweise verbindlich übernehmen'),
                ),
              ]),
            if (writable && !session.pending(pendingKey))
              Wrap(
                spacing: 8,
                children: [
                  FilledButton(
                    onPressed: busy ? null : () => present(() => edit('net')),
                    child: const Text('Belegte Nettozahlungen übernehmen'),
                  ),
                  OutlinedButton(
                    onPressed: busy
                        ? null
                        : () => present(() => edit('remittance')),
                    child: const Text('Belegte Abführungen übernehmen'),
                  ),
                ],
              ),
            card('Private Zahlungsquellen', [
              for (final source in businessItems(p['net_sources']))
                ListTile(
                  title: Text(
                    '${source['month']} · ${source['eligible'] == true ? 'Vollständiger Nachweis' : 'Noch nicht übernehmbar'}',
                  ),
                  subtitle: Text(
                    '${businessItems(source['payments']).where((p) => p['already_imported'] == true).length} von ${(source['payments'] as List).length} Teilen bereits übernommen\n${(source['issues'] as List).join(', ')}',
                  ),
                ),
            ]),
            card('Unternehmensweite Übernahmen', [
              for (final batch in businessItems(s['batches']))
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${batch['kind'] == 'net' ? 'Nettozahlungen' : 'Abführungen'} · Fassung ${batch['revision']}',
                    ),
                    projection(businessMap(batch['public_source'])),
                    TextButton(
                      onPressed: busy
                          ? null
                          : () => present(() => detail(batch)),
                      child: const Text('Privaten Übernahmenachweis öffnen'),
                    ),
                  ],
                ),
            ]),
          ],
        ],
      ),
    );
  }
}

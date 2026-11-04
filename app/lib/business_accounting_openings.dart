import 'dart:convert';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting_openings_contract.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';
import 'offline_vault.dart' show offlineId;

export 'business_accounting_openings_contract.dart';

class BusinessOpeningBalancesPage extends StatefulWidget {
  const BusinessOpeningBalancesPage({
    super.key,
    required this.session,
    this.accountId,
    this.pickFile,
    this.exportFile,
  });
  final BusinessSession session;
  final String? accountId;
  final Future<XFile?> Function()? pickFile;
  final Future<void> Function(VerifiedMailAttachment)? exportFile;
  @override
  State<BusinessOpeningBalancesPage> createState() =>
      _BusinessOpeningBalancesPageState();
}

class _BusinessOpeningBalancesPageState
    extends State<BusinessOpeningBalancesPage>
    with WidgetsBindingObserver {
  final asOf = TextEditingController(
    text: DateTime.now().toUtc().toIso8601String().substring(0, 10),
  );
  final amount = TextEditingController(), reason = TextEditingController();
  final scroll = ScrollController();
  Map<String, dynamic>? state, sources, liquidity, preview, body;
  List<Map<String, dynamic>> history = [];
  String? accountId, error, message;
  String sourceChoice = '';
  bool backgrounded = false;
  bool busy = false,
      denied = false,
      editing = false,
      atStart = false,
      accepted = false;
  int epoch = 0;
  Object? generation;
  String? token;
  BusinessSession get session => widget.session;
  bool get readable => openingReadable(session) && !denied && !backgrounded;
  bool get writable =>
      readable &&
      openingWritable(session) &&
      state?['can_prepare'] == true &&
      !busy &&
      session.error == null;
  bool get pending => session.pendingOpeningKeys.isNotEmpty;
  Map<String, dynamic>? get current => state == null
      ? null
      : businessItems(state!['items'])
            .where((v) => v['account_id'] == accountId)
            .firstOrNull;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    session.addListener(changed);
    accountId = widget.accountId;
    token = session.api.token;
    generation = session.generation;
    load();
  }

  @override
  void didUpdateWidget(covariant BusinessOpeningBalancesPage old) {
    super.didUpdateWidget(old);
    if (!identical(old.session, session) || old.accountId != widget.accountId) {
      old.session.removeListener(changed);
      session.addListener(changed);
      clear();
      accountId = widget.accountId;
      token = session.api.token;
      generation = session.generation;
      load();
    }
  }

  void clearDraft() {
    editing = atStart = accepted = false;
    sourceChoice = '';
    amount.clear();
    reason.clear();
    preview = body = null;
  }

  void clear() {
    epoch++;
    error = message = null;
    state = sources = liquidity = null;
    history = [];
    busy = false;
    clearDraft();
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!openingReadable(session) ||
          token != session.api.token ||
          generation != session.generation) {
        clear();
        generation = session.generation;
        token = session.api.token;
      } else if (!openingWritable(session)) {
        clearDraft();
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState value) {
    if (!mounted) return;
    if ([
      AppLifecycleState.paused,
      AppLifecycleState.hidden,
      AppLifecycleState.detached,
    ].contains(value)) {
      setState(() {
        backgrounded = true;
        clear();
        denied = true;
        error = "Nach dem Hintergrundwechsel den aktuellen Finanzzugriff neu laden.";
      });
    } else if (value == AppLifecycleState.resumed) {
      setState(() => backgrounded = false);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    epoch++;
    session.removeListener(changed);
    for (final c in [asOf, amount, reason]) {
      c.dispose();
    }
    scroll.dispose();
    super.dispose();
  }

  bool sameContext(int stamp) =>
      mounted &&
      stamp == epoch &&
      readable &&
      token == session.api.token &&
      generation == session.generation;
  void failure(Object e) {
    if (!mounted) return;
    setState(() {
      if (e is ApiException && [401, 403, 404].contains(e.status)) {
        clear();
        denied = true;
      } else {
        preview = body = null;
        accepted = false;
      }
      error = e is ApiException
          ? e.message
          : e is FormatException
          ? e.message
          : 'Der Anfangsbestandsnachweis konnte nicht sicher geprüft werden.';
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) scroll.jumpTo(0);
    });
  }

  Future<Map<String, dynamic>> fresh({bool write = false}) async {
    final stamp = epoch;
    await session.load();
    if (!sameContext(stamp) || session.error != null || session.loading)
      throw const ApiException(
        403,
        'Der aktuelle globale Finanzzugriff ist nicht mehr freigegeben.',
      );
    if (write && !openingWritable(session))
      throw const ApiException(
        403,
        'Aktuelle Rechte zur Bestandsbestätigung fehlen.',
      );
    final value = openingState(await session.read(openingPath));
    if (!sameContext(stamp))
      throw const ApiException(403, 'Der Finanzkontext wurde geändert.');
    if (write && value['can_prepare'] != true)
      throw const ApiException(
        423,
        'Anfangsbestände sind derzeit nicht zur Bearbeitung freigegeben.',
      );
    return value;
  }

  Future<void> load() async {
    if (!openingReadable(session) || backgrounded) return;
    final stamp = ++epoch;
    setState(() {
      busy = true;
      error = null;
      denied = false;
      clearDraft();
      state = sources = liquidity = null;
      history = [];
    });
    try {
      final date = openingDate(asOf.text.trim());
      final result = await Future.wait([
        session.read(openingPath),
        session.read('$openingPath/liquidity?as_of=$date'),
      ]);
      if (!sameContext(stamp)) return;
      final next = openingState(result[0]),
          cash = openingLiquidity(result[1], date);
      if (next['revision'] != cash['revision'] ||
          next['state_hash'] != cash['state_hash'])
        throw const ApiException(
          409,
          'Der Bestandsstand wurde während des Ladens geändert. Bitte aktualisieren.',
        );
      Map<String, dynamic>? source;
      List<Map<String, dynamic>> versions = [];
      if (accountId != null &&
          businessItems(next['accounts']).any((v) => v['id'] == accountId)) {
        final values = await Future.wait([
          if (next['profile'] != null)
            session.read('$openingPath/sources?account_id=$accountId'),
          session.read('$openingPath/accounts/$accountId/history'),
        ]);
        if (next['profile'] != null)
          source = openingSources(values[0], next, accountId!);
        versions = businessItems(openingHistory(values.last, accountId!));
        final stored = businessItems(next['items'])
            .where((v) => v['account_id'] == accountId)
            .firstOrNull;
        if (!openingSame(stored, versions.lastOrNull))
          throw const ApiException(
            409,
            'Die Kontohistorie wurde geändert. Bitte aktualisieren.',
          );
      } else {
        accountId = null;
      }
      if (!sameContext(stamp)) return;
      final latest = await fresh();
      if (!sameContext(stamp)) return;
      if (latest['revision'] != next['revision'] ||
          latest['state_hash'] != next['state_hash'])
        throw const ApiException(
          409,
          'Der Bestandsstand wurde während der Quellenprüfung geändert. Bitte aktualisieren.',
        );
      setState(() {
        state = next;
        liquidity = cash;
        sources = source;
        history = versions;
      });
    } catch (e) {
      if (mounted && stamp == epoch) failure(e);
    } finally {
      if (mounted && stamp == epoch) setState(() => busy = false);
    }
  }

  Future<void> run(Future<void> Function(int) task) async {
    if (busy || !readable) return;
    final stamp = epoch;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      await task(stamp);
    } catch (e) {
      if (mounted && stamp == epoch) failure(e);
    } finally {
      if (mounted && stamp == epoch) setState(() => busy = false);
    }
  }

  Future<void> upload() => run((stamp) async {
    if (pending || accountId == null) return;
    final account = accountId!;
    await fresh(write: true);
    if (!sameContext(stamp)) return;
    final file =
        await (widget.pickFile?.call() ??
            openFile(
              acceptedTypeGroups: [
                const XTypeGroup(
                  label: 'Anfangsbestandsoriginal',
                  extensions: ['pdf', 'png', 'jpg', 'jpeg'],
                ),
              ],
            ));
    if (file == null || !sameContext(stamp)) return;
    final size = await file.length();
    if (size < 1 || size > 5 * 1024 * 1024)
      throw const FormatException(
        'PDF, PNG oder JPEG mit 1 Byte bis 5 MiB auswählen.',
      );
    final bytes = await file.readAsBytes(),
        extension = file.name.split('.').last.toLowerCase();
    final media = {
      'pdf': 'application/pdf',
      'png': 'image/png',
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
    }[extension];
    if (media == null || bytes.length != size)
      throw const FormatException(
        'Die Originaldatei hat kein unterstütztes Format oder wurde geändert.',
      );
    await fresh(write: true);
    if (!sameContext(stamp) || account != accountId || pending) return;
    final data = {
      'account_id': account,
      'filename': file.name,
      'media_type': media,
      'content_base64': base64Encode(bytes),
    };
    await session.command(
      'accounting-opening-original-${offlineId()}',
      '$openingPath/originals',
      data,
      validateResult: openingOriginalReceipt(data),
    );
    if (!sameContext(stamp)) return;
    await load();
    if (mounted && readable)
      setState(
        () => message = 'Original gespeichert. Den passenden Nachweis ausdrücklich auswählen.',
      );
  });
  void edit() {
    if (!writable || pending || sources == null) return;
    setState(() {
      clearDraft();
      editing = true;
      error = message = null;
    });
  }

  Future<void> prepare({bool voiding = false}) => run((stamp) async {
    if (pending || sources == null || accountId == null) return;
    final old = current;
    Map<String, dynamic> data;
    if (voiding) {
      if (old == null || old['status'] != 'active') return;
      data = {for (final key in openingFields) key: old[key]};
      data['status'] = 'void';
    } else {
      Map<String, dynamic>? source;
      String? bankAmount;
      if (sourceChoice.startsWith('original:')) {
        final o = businessItems(sources!['originals'])
            .where((v) => 'original:${v['id']}' == sourceChoice)
            .firstOrNull;
        if (o != null)
          source = {
            'kind': 'original',
            'original_id': o['id'],
            'sha256': o['sha256'],
            'evidence_type': sources!['original_evidence_type'],
            'at_start_of_day': atStart,
          };
      } else if (sourceChoice.startsWith('bank:')) {
        final index = int.tryParse(sourceChoice.substring(5));
        final list = businessItems(sources!['bank_statements']);
        if (index != null && index >= 0 && index < list.length) {
          source = businessMap(list[index]['source']);
          bankAmount = list[index]['amount'] as String;
        }
      }
      if (source == null || source['kind'] == 'original' && !atStart)
        throw const FormatException(
          'Den Originalnachweis und den Bestand vor der ersten Bewegung ausdrücklich bestätigen.',
        );
      data = {
        'account_id': accountId,
        'account_revision': sources!['account']['revision'],
        'profile_ref': sources!['profile_ref'],
        'status': 'active',
        'opening_date': sources!['opening_date'],
        'amount': bankAmount ?? openingAmount(amount.text),
        'source': source,
      };
    }
    if (reason.text.trim().isEmpty)
      throw const FormatException(
        'Einen nachvollziehbaren Prüf-, Korrektur- oder Aufhebungsgrund angeben.',
      );
    data.addAll({
      'expected_revision': state!['revision'],
      'state_hash': state!['state_hash'],
      'reason': reason.text.trim(),
    });
    final verified = await fresh(write: true);
    if (!sameContext(stamp) || pending) return;
    if (verified['revision'] != state!['revision'] ||
        verified['state_hash'] != state!['state_hash'])
      throw const ApiException(
        409,
        'Der Bestandsstand wurde geändert. Bitte neu laden und prüfen.',
      );
    final checked = openingPreview(
      await session.previewOpeningBalance(data),
      data,
    );
    if (!sameContext(stamp) || pending) return;
    final latest = await fresh(write: true);
    if (!sameContext(stamp) || pending) return;
    if (latest['revision'] != data['expected_revision'] ||
        latest['state_hash'] != data['state_hash'])
      throw const ApiException(
        409,
        'Der Bestandsstand wurde während der Vorschau geändert. Bitte neu prüfen.',
      );
    setState(() {
      preview = checked;
      body = {
        ...data,
        'confirmation': true,
        'preview_hash': checked['preview_hash'],
      };
      accepted = false;
      editing = false;
    });
  });
  Future<void> confirm() => run((stamp) async {
    if (body == null || preview == null || !accepted || pending) return;
    final captured = Map<String, dynamic>.from(body!),
        proof = Map<String, dynamic>.from(preview!);
    await fresh(write: true);
    if (!sameContext(stamp) || !accepted || pending) return;
    await session.command(
      'accounting-opening-confirm',
      '$openingPath/confirm',
      captured,
      validateResult: openingReceipt(proof),
    );
    if (!sameContext(stamp)) return;
    await load();
    if (mounted && readable)
      setState(
        () => message = proof['status'] == 'void'
            ? 'Anfangsbestand belegt aufgehoben; ursprüngliche Fassungen bleiben erhalten.'
            : 'Anfangsbestand bestätigt. Liquidität wurde neu aus den belegten Bewegungen ermittelt.',
      );
  });
  Future<void> repeat(String key) => run((stamp) async {
    await session.repeatOpeningCommand(key);
    if (sameContext(stamp)) await load();
  });
  Future<void> original(Map<String, dynamic> proof) => run((stamp) async {
    await fresh();
    if (!sameContext(stamp)) return;
    final isOwn = proof['kind'] == 'original',
        meta = businessMap(proof['original']);
    final path = isOwn
        ? '$openingPath/originals/${meta['id']}'
        : '/bank/statements/${proof['statement_id']}/original';
    final media = isOwn ? meta['media_type'] as String : 'text/csv';
    final bytes = await session.api.bytes(
      session.path(path),
      mediaType: media,
      maxBytes: 5 * 1024 * 1024,
    );
    if (isOwn) {
      openingVerifyBytes(bytes, meta);
    } else if (openingDigest(bytes) != proof['file_sha256']) {
      throw const ApiException(
        0,
        'Das Bankoriginal stimmt nicht mit der ausgewählten Bestandsquelle überein.',
      );
    }
    await fresh();
    if (!sameContext(stamp)) return;
    final file = VerifiedMailAttachment(
      bytes: Uint8List.fromList(bytes),
      filename: isOwn
          ? meta['filename']
          : 'kontoauszug-${proof['statement_id']}.csv',
      mediaType: media,
      sha256: isOwn ? meta['sha256'] : proof['file_sha256'],
    );
    if (widget.exportFile != null) {
      await widget.exportFile!(file);
    } else {
      if (!mounted) return;
      await exportMailAttachment(context, file, () => sameContext(stamp));
    }
  });
  Widget card(List<Widget> items) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: items
            .map(
              (v) =>
                  Padding(padding: const EdgeInsets.only(bottom: 8), child: v),
            )
            .toList(),
      ),
    ),
  );
  Widget money(String label, dynamic value) => ListTile(
    contentPadding: EdgeInsets.zero,
    dense: true,
    title: Text(label),
    subtitle: Text(value == null ? 'Unbekannt' : businessMoney(value)),
  );
  Widget action(String label, VoidCallback? callback) =>
      OutlinedButton(onPressed: busy ? null : callback, child: Text(label));
  Widget entry(Map<String, dynamic> v, {bool historical = false}) => card([
    Text(
      '${historical ? 'Historische Fassung' : 'Bestätigter Bestand'} ${v['revision']} · ${v['status'] == 'active' ? 'Gültig' : 'Aufgehoben'}',
      style: Theme.of(context).textTheme.titleMedium,
    ),
    money('Belegter Anfangsbestand', v['amount']),
    Text(
      'Vor der ersten Bewegung am ${businessDate(v['opening_date'])} · Europe/Berlin',
    ),
    Text('Grund: ${v['reason']}'),
    Text(
      v['source']['kind'] == 'original'
          ? 'Original: ${v['source_proof']['original']['filename']}'
          : 'Bankauszug: ${v['source_proof']['statement_reference']}',
    ),
    action(
      'Unverändertes Bestandsoriginal öffnen',
      () => original(businessMap(v['source_proof'])),
    ),
    if (!historical && writable && !pending)
      action('Anfangsbestand berichtigen', edit),
  ]);
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Anfangsbestände und Liquidität'),
      actions: [
        IconButton(
          onPressed: busy ? null : load,
          tooltip: 'Stand aktualisieren',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !readable
        ? BusinessEmpty(
            'Anfangsbestände nicht freigegeben',
            error ?? 'Globale Buchhaltungs-, Finanz- und Bankleserechte sind erforderlich.',
          )
        : ListView(
            controller: scroll,
            padding: const EdgeInsets.all(16),
            children: [
              const Notice(
                'Bestätigte Anfangsbestände und erfasste Geldbewegungen ergeben den ausgewiesenen Bestand. Fehlende oder widersprüchliche Nachweise bleiben unbekannt. Eine Bestätigung erzeugt keine Zahlung und keine EÜR-Steuerbuchung.',
              ),
              if (error != null) Notice(error!, error: true),
              if (message != null) Notice(message!),
              if (busy) const LinearProgressIndicator(),
              for (final key in session.pendingOpeningKeys)
                card([
                  const Text(
                    'Die Antwort auf einen ursprünglichen Auftrag ist noch offen.',
                  ),
                  action(
                    'Ursprünglichen Bestandsauftrag unverändert erneut senden',
                    openingWritable(session) ? () => repeat(key) : null,
                  ),
                ]),
              TextField(
                controller: asOf,
                enabled: !busy,
                decoration: const InputDecoration(
                  labelText: 'Bestandsstichtag (JJJJ-MM-TT)',
                ),
              ),
              action('Liquidität zum Stichtag prüfen', load),
              if (liquidity != null)
                card([
                  Text(
                    'Liquidität am ${businessDate(liquidity!['as_of'])}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  money(
                    'Gesamtbestand der erfassten Geldkonten',
                    liquidity!['balance_total'],
                  ),
                  if (liquidity!['complete_for_recorded_accounts'] != true) ...[
                    money(
                      'Summe der einzeln belegten Bestände',
                      liquidity!['known_balance_sum'],
                    ),
                    const Notice(
                      'Ein vollständiger Gesamtbestand ist wegen fehlender oder widersprüchlicher Quellen noch nicht belegt.',
                    ),
                  ],
                  for (final issue in businessItems(liquidity!['issues']))
                    Text(_issue('${issue['code']}')),
                  if (businessItems(liquidity!['unresolved_cash_sources'])
                      .isNotEmpty)
                    const Notice(
                      'Vorhandene Zahlungsquellen wurden noch nicht vollständig als Geldfluss übernommen.',
                    ),
                  for (final row in businessItems(liquidity!['accounts']))
                    ExpansionTile(
                      title: Text(
                        '${row['account']['code']} · ${row['account']['name']}',
                      ),
                      subtitle: Text(
                        row['balance'] == null
                            ? 'Bestand unbekannt'
                            : businessMoney(row['balance']),
                      ),
                      children: [
                        money('Anfangsbestand', row['opening_balance']),
                        money('Zuflüsse', row['inflows']),
                        money('Abflüsse', row['outflows']),
                        money(
                          'Rechnerischer Bestand vor Quellenprüfung',
                          row['calculated_balance'],
                        ),
                        for (final issue in businessItems(row['issues']))
                          Text(_issue('${issue['code']}')),
                        for (final check in businessItems(
                          row['bank_connections'],
                        ))
                          Text(
                            'Auszugsanschluss ${businessDate(check['date'])}: ${check['matches'] == true ? 'stimmt überein' : 'Widerspruch'} · Auszug ${businessMoney(check['statement_balance'])} / erfasst ${businessMoney(check['recorded_balance'])}',
                          ),
                        for (final m in businessItems(row['movements']))
                          Text(
                            '${businessDate(m['date'])} · ${m['direction'] == 'in' ? 'Zufluss' : 'Abfluss'} ${businessMoney(m['amount'])}',
                          ),
                      ],
                    ),
                ]),
              if (state != null) ...[
                if (state!['profile'] == null)
                  const Notice(
                    'Zuerst einen ausdrücklichen Buchführungsbeginn im Buchführungsprofil bestätigen.',
                  ),
                DropdownButtonFormField<String>(
                  key: ValueKey('opening-account-$accountId'),
                  initialValue: accountId,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'Geldkonto'),
                  items: [
                    for (final a in businessItems(state!['accounts']))
                      DropdownMenuItem(
                        value: '${a['id']}',
                        child: Text(
                          '${a['code']} · ${a['name']}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: busy
                      ? null
                      : (id) {
                          setState(() => accountId = id);
                          load();
                        },
                ),
                if (sources != null) ...[
                  Text(
                    'Bestandsbeginn aus bestätigtem Buchführungsprofil: ${businessDate(sources!['opening_date'])}',
                  ),
                  if (current != null) entry(current!),
                  if (writable && !pending) ...[
                    action('Bestandsoriginal hochladen', upload),
                    if (!editing && preview == null)
                      action('Anfangsbestand aus Nachweisen prüfen', edit),
                  ],
                  if (editing && writable && !pending) ...[
                    DropdownButtonFormField<String>(
                      key: ValueKey('opening-source-$sourceChoice'),
                      initialValue: sourceChoice.isEmpty ? null : sourceChoice,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Unveränderten Bestandsnachweis auswählen',
                      ),
                      items: [
                        for (final o in businessItems(sources!['originals']))
                          DropdownMenuItem(
                            value: 'original:${o['id']}',
                            child: Text(
                              'Original · ${o['filename']}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        for (final (i, b) in businessItems(
                          sources!['bank_statements'],
                        ).indexed)
                          DropdownMenuItem(
                            value: 'bank:$i',
                            child: Text(
                              'Bankauszug · ${b['statement_reference']} · ${businessMoney(b['amount'])}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                      ],
                      onChanged: (v) {
                        setState(() {
                          sourceChoice = v ?? '';
                          amount.clear();
                          if (sourceChoice.startsWith('bank:')) {
                            final index = int.parse(sourceChoice.substring(5));
                            amount.text = businessItems(
                              sources!['bank_statements'],
                            )[index]['amount'];
                          }
                          preview = body = null;
                          accepted = false;
                        });
                      },
                    ),
                    TextField(
                      controller: amount,
                      readOnly: sourceChoice.startsWith('bank:'),
                      decoration: InputDecoration(
                        labelText: 'Belegter Anfangsbestand (EUR)',
                        helperText: sourceChoice.startsWith('bank:')
                            ? 'Unveränderter Saldo aus dem ausgewählten Bankauszug.'
                            : null,
                      ),
                      keyboardType: const TextInputType.numberWithOptions(
                        signed: true,
                        decimal: true,
                      ),
                    ),
                    CheckboxListTile(
                      value: atStart,
                      onChanged: (v) => setState(() => atStart = v == true),
                      title: const Text(
                        'Das Original belegt den Bestand vor der ersten Bewegung dieses Stichtags.',
                      ),
                    ),
                    TextField(
                      controller: reason,
                      decoration: const InputDecoration(
                        labelText: 'Prüf- oder Korrekturgrund',
                      ),
                      maxLength: 1000,
                    ),
                    action(
                      'Anfangsbestand unverbindlich prüfen',
                      () => prepare(),
                    ),
                    if (current?['status'] == 'active')
                      action(
                        'Unveränderten bisherigen Anfangsbestand zur Aufhebung prüfen',
                        () => prepare(voiding: true),
                      ),
                  ],
                ],
              ],
              if (preview != null && writable && !pending)
                card([
                  Text(
                    preview!['status'] == 'void'
                        ? 'Aufhebung prüfen'
                        : 'Anfangsbestand prüfen',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  Text(
                    '${preview!['account']['code']} · ${preview!['account']['name']}',
                  ),
                  money('Unverändert geprüfter Betrag', preview!['amount']),
                  Text(
                    'Vor der ersten Bewegung am ${businessDate(preview!['opening_date'])}',
                  ),
                  Text('Grund: ${preview!['reason']}'),
                  action(
                    'Geprüftes Bestandsoriginal öffnen',
                    () => original(businessMap(preview!['source_proof'])),
                  ),
                  CheckboxListTile(
                    value: accepted,
                    onChanged: (v) => setState(() => accepted = v == true),
                    title: const Text(
                      'Ich bestätige genau diesen Bestand, Stichtag und Originalnachweis.',
                    ),
                  ),
                  FilledButton(
                    onPressed: accepted ? confirm : null,
                    child: Text(
                      preview!['status'] == 'void'
                          ? 'Anfangsbestand belegt aufheben'
                          : 'Geprüften Anfangsbestand bestätigen',
                    ),
                  ),
                ]),
              if (accountId != null) ...[
                const SizedBox(height: 16),
                Text(
                  'Unveränderte Kontohistorie',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                if (history.isEmpty && !busy)
                  const Text('Noch kein bestätigter Anfangsbestand vorhanden.'),
                for (final value in history) entry(value, historical: true),
              ],
            ],
          ),
  );
}

String _issue(String code) =>
    const {
      'opening_balance_missing': 'Ein bestätigter Anfangsbestand fehlt.',
      'opening_profile_changed':
          'Das Buchführungsprofil wurde seit der Bestätigung geändert.',
      'as_of_before_opening':
          'Der gewählte Stichtag liegt vor dem Anfangsbestand.',
      'bank_statement_connection_mismatch': 'Ein Bankauszug widerspricht dem belegten Anfangsbestand und den erfassten Bewegungen.',
      'restore_reconciliation_pending':
          'Die finanzielle Prüfung nach Wiederherstellung steht noch aus.',
      'cash_balance_negative': 'Die erfassten Bewegungen ergeben einen negativen Kassenbestand. Die fehlenden oder widersprüchlichen Nachweise müssen geklärt werden.',
    }[code] ??
    'Eine Quelle benötigt weitere Klärung.';

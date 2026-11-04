import 'dart:convert';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting_euer.dart';
import 'business_accounting_historical_assets_contract.dart';
import 'business_accounting_openings_contract.dart'
    show openingDate, openingSame;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';
import 'offline_vault.dart' show offlineId;

export 'business_accounting_historical_assets_contract.dart';

const _labels = {
  'inventory_number': 'Betriebliche Inventarnummer',
  'description': 'Bezeichnung der historischen Anlage',
  'acquired_on': 'Ursprüngliche Anschaffung (JJJJ-MM-TT)',
  'use_start': 'Ursprünglicher AfA-/Nutzungsbeginn (JJJJ-MM-TT)',
  'life_months': 'Belegte ursprüngliche Nutzungsdauer (Monate)',
  'acquisition_gross': 'Ursprüngliche Bruttokosten (EUR)',
  'deductible_input_tax': 'Abziehbare ursprüngliche Vorsteuer (EUR)',
  'cost_basis': 'Belegte betriebliche Kostenbasis (EUR)',
  'depreciation_before_start_year': 'Belegte AfA vor dem Übernahmejahr (EUR)',
  'depreciation_in_start_year': 'Bereits im Übernahmejahr gebuchte AfA (EUR)',
  'opening_book_value': 'Belegter Restbuchwert am Übernahmestichtag (EUR)',
  'account': 'Geprüftes SKR04-Anlagenkonto',
  'position': 'Eindeutige Position im Anlagenoriginal',
  'history_through': 'Historie belegt bis (JJJJ-MM-TT)',
  'reason': 'Prüf-, Korrektur- oder Aufhebungsgrund',
};
const _moneyFields = [
  'acquisition_gross',
  'deductible_input_tax',
  'cost_basis',
  'depreciation_before_start_year',
  'depreciation_in_start_year',
  'opening_book_value',
];

class BusinessHistoricalAssetsPage extends StatefulWidget {
  const BusinessHistoricalAssetsPage({
    super.key,
    required this.session,
    this.assetKey,
    this.pickFile,
    this.exportFile,
  });
  final BusinessSession session;
  final String? assetKey;
  final Future<XFile?> Function()? pickFile;
  final Future<void> Function(VerifiedMailAttachment)? exportFile;
  @override
  State<BusinessHistoricalAssetsPage> createState() =>
      _BusinessHistoricalAssetsPageState();
}

class _BusinessHistoricalAssetsPageState
    extends State<BusinessHistoricalAssetsPage>
    with WidgetsBindingObserver {
  final fields = {for (final k in _labels.keys) k: TextEditingController()};
  final year = TextEditingController(text: '${DateTime.now().year}'),
      scroll = ScrollController();
  Map<String, dynamic>? state, identity, preview, body, report;
  List<Map<String, dynamic>> history = [];
  String? selected, error, message, originalId;
  String rounding = '';
  int epoch = 0;
  Object? generation;
  String? token;
  bool busy = false,
      denied = false,
      backgrounded = false,
      editing = false,
      confirmedHistory = false,
      accepted = false;
  BusinessSession get session => widget.session;
  bool get readable =>
      historicalAssetsReadable(session) && !denied && !backgrounded;
  bool get rights => readable && historicalAssetsWritable(session);
  bool get writable =>
      rights && state?['can_prepare'] == true && !busy && session.error == null;
  bool get pending => session.pendingHistoricalAssetKeys.isNotEmpty;
  Map<String, dynamic>? get current => state == null
      ? null
      : businessItems(state!['items'])
            .where((r) => r['asset_key'] == selected)
            .firstOrNull;
  String? get draftKey {
    final id = identity;
    if (id == null ||
        id['inventory_number'] != fields['inventory_number']!.text)
      return null;
    return id['asset_key'] as String;
  }

  bool get sameSelectedDraft =>
      selected != null && current != null && draftKey == selected;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    session.addListener(changed);
    selected = widget.assetKey;
    token = session.api.token;
    generation = session.generation;
    load();
  }

  @override
  void didUpdateWidget(covariant BusinessHistoricalAssetsPage old) {
    super.didUpdateWidget(old);
    if (!identical(old.session, session) || old.assetKey != widget.assetKey) {
      old.session.removeListener(changed);
      session.addListener(changed);
      clear();
      selected = widget.assetKey;
      token = session.api.token;
      generation = session.generation;
      load();
    }
  }

  void clearDraft() {
    for (final c in fields.values) c.clear();
    identity = preview = body = null;
    originalId = null;
    rounding = '';
    editing = confirmedHistory = accepted = false;
  }

  void clear() {
    epoch++;
    state = report = null;
    history = [];
    busy = false;
    error = message = null;
    clearDraft();
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!historicalAssetsReadable(session) ||
          token != session.api.token ||
          generation != session.generation) {
        clear();
        token = session.api.token;
        generation = session.generation;
      } else if (!historicalAssetsWritable(session)) {
        clearDraft();
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState value) {
    if (!mounted) return;
    if ([
      AppLifecycleState.hidden,
      AppLifecycleState.paused,
      AppLifecycleState.detached,
    ].contains(value)) {
      setState(() {
        clear();
        backgrounded = true;
        denied = true;
        error = 'Nach dem Hintergrundwechsel den aktuellen Anlagenzugriff neu laden.';
      });
    } else if (value == AppLifecycleState.resumed) {
      setState(() => backgrounded = false);
    }
  }

  @override
  void dispose() {
    epoch++;
    WidgetsBinding.instance.removeObserver(this);
    session.removeListener(changed);
    for (final c in fields.values) c.dispose();
    year.dispose();
    scroll.dispose();
    super.dispose();
  }

  bool same(int stamp) =>
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
          : 'Der historische Anlagenstand konnte nicht sicher geprüft werden.';
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) scroll.jumpTo(0);
    });
  }

  int selectedYear() {
    final v = int.tryParse(year.text.trim());
    if (v == null || v < 1900 || v > 2200)
      throw const FormatException(
        'Auswertungsjahr zwischen 1900 und 2200 eingeben.',
      );
    return v;
  }

  Future<Map<String, dynamic>> fresh({bool write = false}) async {
    final stamp = epoch;
    await session.load();
    if (!same(stamp) || session.error != null || session.loading)
      throw const ApiException(
        403,
        'Aktuelle globale Finanz- und Buchführungsrechte fehlen.',
      );
    if (write && !historicalAssetsWritable(session))
      throw const ApiException(
        403,
        'Aktuelle Rechte zur Anlagenübernahme fehlen.',
      );
    final next = historicalAssetState(await session.read(historicalAssetPath));
    if (!same(stamp))
      throw const ApiException(403, 'Der Anlagenkontext wurde geändert.');
    if (write && next['can_prepare'] != true)
      throw const ApiException(
        423,
        'Historische Anlagen sind derzeit nicht zur Bearbeitung freigegeben.',
      );
    return next;
  }

  Future<void> load() async {
    if (!historicalAssetsReadable(session) || backgrounded) return;
    final stamp = ++epoch;
    setState(() {
      busy = true;
      denied = false;
      error = message = null;
      clearDraft();
      state = report = null;
      history = [];
    });
    try {
      final next = historicalAssetState(
        await session.read(historicalAssetPath),
      );
      if (!same(stamp)) return;
      final key = selected;
      List<Map<String, dynamic>> versions = [];
      if (key != null) {
        versions = businessItems(
          historicalAssetHistory(
            await session.read(historicalAssetHistoryPath(key)),
            key,
          ),
        );
        final existing = businessItems(next['items'])
            .where((r) => r['asset_key'] == key)
            .firstOrNull;
        if (!openingSame(existing, versions.lastOrNull))
          throw const ApiException(
            409,
            'Die Anlagenhistorie wurde geändert. Bitte neu laden.',
          );
      }
      Map<String, dynamic>? annual;
      if (businessEuerReadable(session)) {
        final y = selectedYear();
        annual = businessMap(await session.read('$euerPath/report?year=$y'));
        if (annual['year'] != y)
          throw const ApiException(
            0,
            'Die Jahresauswertung gehört nicht zum gewählten Jahr.',
          );
        historicalAssetReport(annual);
      }
      if (!same(stamp)) return;
      final latest = await fresh();
      if (!same(stamp)) return;
      if (next['revision'] != latest['revision'] ||
          next['state_hash'] != latest['state_hash'])
        throw const ApiException(
          409,
          'Der Anlagenstand wurde während der Quellenprüfung geändert. Bitte neu laden.',
        );
      setState(() {
        state = next;
        history = versions;
        report = annual;
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

  void edit({bool correction = false}) {
    if (!writable || pending) return;
    final old = correction ? current : null;
    setState(() {
      clearDraft();
      editing = true;
      error = message = null;
      if (old != null) {
        final asset = businessMap(old['asset']);
        for (final k in historicalAssetFields) {
          if (fields.containsKey(k)) fields[k]!.text = '${asset[k]}';
        }
        for (final k in ['position', 'history_through'])
          fields[k]!.text = old['source'][k];
        rounding = asset['rounding'];
        originalId = old['source']['original_id'];
        identity = {
          'schema_version': 1,
          'inventory_number': asset['inventory_number'],
          'asset_key': old['asset_key'],
        };
      }
    });
  }

  Future<void> identify() => run((stamp) async {
    if (pending) return;
    final number = historicalAssetText(
      fields['inventory_number']!.text,
      'Inventarnummer',
      100,
    );
    await fresh(write: true);
    if (!same(stamp)) return;
    final answer = historicalAssetIdentity(
      await session.api.call(session.path('$historicalAssetPath/identity'), {
        'inventory_number': number,
      }),
      number,
    );
    await fresh(write: true);
    if (!same(stamp) || number != fields['inventory_number']!.text) return;
    setState(() {
      identity = answer;
      originalId = null;
      message = 'Inventaridentität bestätigt. Das passende historische Original ausdrücklich auswählen oder hochladen.';
    });
  });
  Future<void> upload() => run((stamp) async {
    if (pending || draftKey == null) return;
    final key = draftKey!, number = fields['inventory_number']!.text;
    await fresh(write: true);
    if (!same(stamp)) return;
    final file =
        await (widget.pickFile?.call() ??
            openFile(
              acceptedTypeGroups: [
                const XTypeGroup(
                  label: 'Historisches Anlagenoriginal',
                  extensions: ['pdf', 'png', 'jpg', 'jpeg'],
                ),
              ],
            ));
    if (file == null || !same(stamp)) return;
    final size = await file.length();
    if (size < 1 || size > 5 * 1024 * 1024)
      throw const FormatException(
        'PDF, PNG oder JPEG mit 1 Byte bis 5 MiB auswählen.',
      );
    final bytes = await file.readAsBytes(),
        media = {
          'pdf': 'application/pdf',
          'png': 'image/png',
          'jpg': 'image/jpeg',
          'jpeg': 'image/jpeg',
        }[file.name.split('.').last.toLowerCase()];
    if (media == null || bytes.length != size)
      throw const FormatException(
        'Die unveränderte Originaldatei hat kein unterstütztes Format.',
      );
    await fresh(write: true);
    if (!same(stamp) ||
        key != draftKey ||
        number != fields['inventory_number']!.text ||
        pending)
      return;
    final request = {
      'asset_key': key,
      'filename': file.name,
      'media_type': media,
      'content_base64': base64Encode(bytes),
    };
    await session.command(
      'historical-asset-original-${offlineId()}',
      '$historicalAssetPath/originals',
      request,
      validateResult: historicalAssetOriginalReceipt(request),
    );
    if (!same(stamp)) return;
    final next = await fresh(write: true);
    if (!same(stamp)) return;
    setState(() {
      state = next;
      message = 'Historisches Original gespeichert. Den Beleg und seine eindeutige Position ausdrücklich wählen.';
    });
  });
  Future<void> prepare({bool voiding = false}) => run((stamp) async {
    if (pending || state == null) return;
    Map<String, dynamic> input;
    if (voiding) {
      final old = current;
      if (old == null || old['status'] != 'active') return;
      input = {for (final k in historicalAssetInput) k: old[k]};
      input['status'] = 'void';
    } else {
      if (!confirmedHistory || draftKey == null || originalId == null)
        throw const FormatException(
          'Inventaridentität, Original und unterstützte unveränderte Historie ausdrücklich bestätigen.',
        );
      final o = businessItems(state!['originals'])
          .where((v) => v['id'] == originalId && v['asset_key'] == draftKey)
          .firstOrNull;
      if (o == null)
        throw const FormatException(
          'Ein unverändertes Original genau dieser Inventaridentität wählen.',
        );
      final opening = state!['profile']?['profile']?['bookkeeping_start'];
      final data = <String, dynamic>{
        for (final k in [
          'inventory_number',
          'description',
          'acquired_on',
          'use_start',
          'account',
        ])
          k: fields[k]!.text.trim(),
        for (final k in _moneyFields) k: historicalAssetAmount(fields[k]!.text),
        'life_months': int.tryParse(fields['life_months']!.text.trim()),
        'rounding': rounding,
        'asset_kind': 'movable',
        'business_use': 'exclusive_business',
        'method': 'linear',
        'unchanged_linear_history_confirmed': confirmedHistory,
      };
      // Identity is bound to the exact original input, including documented spaces.
      data['inventory_number'] = fields['inventory_number']!.text;
      historicalAssetData(data, opening);
      input = {
        'asset_key': draftKey,
        'profile_ref': state!['profile_ref'],
        'status': 'active',
        'opening_date': opening,
        'asset': data,
        'source': {
          'original_id': o['id'],
          'sha256': o['sha256'],
          'position': historicalAssetText(
            fields['position']!.text.trim(),
            'Originalposition',
            300,
          ),
          'history_through': openingDate(
            fields['history_through']!.text.trim(),
          ),
        },
      };
    }
    input.addAll({
      'expected_revision': state!['revision'],
      'state_hash': state!['state_hash'],
      'reason': historicalAssetText(fields['reason']!.text.trim(), 'Prüfgrund'),
    });
    final currentState = await fresh(write: true);
    if (!same(stamp) || pending) return;
    if (currentState['revision'] != state!['revision'] ||
        currentState['state_hash'] != state!['state_hash'])
      throw const ApiException(
        409,
        'Der Anlagenstand wurde geändert. Bitte neu laden.',
      );
    final proof = historicalAssetPreview(
      await session.previewHistoricalAsset(input),
      input,
    );
    if (!same(stamp)) return;
    final after = await fresh(write: true);
    if (!same(stamp) || pending) return;
    if (after['revision'] != input['expected_revision'] ||
        after['state_hash'] != input['state_hash'])
      throw const ApiException(
        409,
        'Die Anlagenfassung wurde während der Vorschau geändert.',
      );
    setState(() {
      preview = proof;
      body = {
        ...input,
        'confirmation': true,
        'preview_hash': proof['preview_hash'],
      };
      accepted = false;
      editing = false;
    });
  });
  Future<void> confirm() => run((stamp) async {
    if (body == null || preview == null || !accepted || pending) return;
    final input = {...body!}, proof = {...preview!};
    await fresh(write: true);
    if (!same(stamp) || !accepted || pending) return;
    await session.command(
      'historical-asset-confirm',
      '$historicalAssetPath/confirm',
      input,
      validateResult: historicalAssetReceipt(proof),
    );
    if (!same(stamp)) return;
    selected = input['asset_key'];
    await load();
    if (mounted && readable)
      setState(
        () => message = proof['status'] == 'void'
            ? 'Anlagenvortrag ausdrücklich aufgehoben; Originalhistorie bleibt erhalten.'
            : 'Historische Anlage ohne neue Zahlung oder Vorsteuer übernommen. Folge-AfA gesondert prüfen.',
      );
  });
  Future<void> repeat(String key) => run((stamp) async {
    final result = businessMap(await session.repeatHistoricalAssetCommand(key));
    if (same(stamp)) {
      selected = result['asset_key'];
      await load();
    }
  });
  Future<void> original(Map<String, dynamic> meta) => run((stamp) async {
    await fresh();
    if (!same(stamp)) return;
    final bytes = await session.api.bytes(
      session.path(meta['path']),
      mediaType: meta['media_type'],
      maxBytes: 5 * 1024 * 1024,
    );
    historicalAssetVerifyBytes(bytes, meta);
    await fresh();
    if (!same(stamp)) return;
    final file = VerifiedMailAttachment(
      bytes: Uint8List.fromList(bytes),
      filename: meta['filename'],
      mediaType: meta['media_type'],
      sha256: meta['sha256'],
    );
    if (widget.exportFile != null) {
      await widget.exportFile!(file);
    } else {
      if (!mounted) return;
      await exportMailAttachment(context, file, () => same(stamp));
    }
  });
  Future<void> euer({bool depreciation = false}) async {
    final stamp = epoch;
    try {
      await fresh();
      if (!same(stamp)) return;
      final entry = current;
      if (depreciation && (entry == null || entry['status'] != 'active'))
        return;
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => BusinessEuerPage(
            session: session,
            initialHistoricalAssetId: depreciation ? entry!['id'] : null,
            initialYear: selectedYear(),
            initialTab: depreciation ? 'sources' : 'journal',
          ),
        ),
      );
      if (mounted && same(stamp)) await load();
    } catch (e) {
      if (mounted && stamp == epoch) failure(e);
    }
  }

  Widget button(String text, VoidCallback? onTap) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: OutlinedButton(onPressed: onTap, child: Text(text)),
  );
  Widget card(List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final c in children)
            Padding(padding: const EdgeInsets.only(bottom: 8), child: c),
        ],
      ),
    ),
  );
  Widget input(String key, {bool readOnly = false}) => TextField(
    controller: fields[key],
    readOnly: readOnly || busy,
    decoration: InputDecoration(labelText: _labels[key]),
    keyboardType: _moneyFields.contains(key)
        ? const TextInputType.numberWithOptions(decimal: true)
        : key == 'life_months'
        ? TextInputType.number
        : TextInputType.text,
    onChanged: key == 'inventory_number'
        ? (_) => setState(() {
            identity = null;
            originalId = null;
            preview = body = null;
            accepted = false;
          })
        : null,
  );
  Widget assetFacts(Map<String, dynamic> asset) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        '${asset['inventory_number']} · ${asset['description']}',
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      Text(
        'Anschaffung ${businessDate(asset['acquired_on'])} · ursprünglicher Beginn ${businessDate(asset['use_start'])} · ${asset['life_months']} Monate',
      ),
      Text(
        historicalAssetRounding[asset['rounding']] ??
            'Unbekanntes Altverfahren',
      ),
      for (final k in _moneyFields)
        Text('${_labels[k]}: ${businessMoney(asset[k])}'),
      Text('Geprüftes Anlagenkonto: ${asset['account']}'),
    ],
  );
  Widget entryCard(
    Map<String, dynamic> entry, {
    bool historical = false,
  }) => card([
    Text(
      '${entry['status'] == 'active' ? 'Angenommener Vortrag' : 'Ausdrücklich aufgehoben'} · Fassung ${entry['revision']}',
    ),
    assetFacts(businessMap(entry['asset'])),
    Text(
      'Vortrag vor der ersten Bewegung am ${businessDate(entry['opening_date'])}',
    ),
    Text(
      'Original: ${entry['source_proof']['original']['filename']} · ${entry['source']['position']}',
    ),
    Text('Historie bis ${businessDate(entry['source']['history_through'])}'),
    Text('Grund: ${entry['reason']}'),
    button(
      'Unverändertes Anlagenoriginal öffnen',
      busy
          ? null
          : () => original(businessMap(entry['source_proof']['original'])),
    ),
    if (!historical && writable && !pending)
      button('Anlagenvortrag berichtigen', () => edit(correction: true)),
  ]);
  @override
  Widget build(BuildContext context) {
    final annual = report == null
        ? null
        : historicalAssetReport(report)
              .where((r) => r['asset_key'] == selected)
              .firstOrNull;
    final choices = <String>{
      if (state != null)
        ...businessItems(state!['items']).map((v) => v['asset_key'] as String),
      if (state != null)
        ...businessItems(state!['originals'])
            .map((v) => v['asset_key'] as String),
    };
    return Scaffold(
      appBar: AppBar(
        title: const Text('Historische Anlagen'),
        actions: [
          IconButton(
            onPressed: busy ? null : load,
            tooltip: 'Anlagenstand aktualisieren',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !readable
          ? BusinessEmpty(
              'Historische Anlagen nicht freigegeben',
              error ?? 'Aktuelle globale Finanz- und Buchführungsleserechte sind erforderlich.',
            )
          : ListView(
              controller: scroll,
              padding: const EdgeInsets.all(16),
              children: [
                const Notice(
                  'Belegte unverändert lineare bewegliche Anlagen bei ausschließlich betrieblicher Nutzung. Kein Methodenwechsel, GWG, Sonder-AfA, Privatanteil oder Abgang. Die Übernahme erzeugt keine neue Anschaffung, Zahlung oder Vorsteuer. Unpassende oder fehlende Originalwerte müssen fachlich geklärt werden.',
                ),
                if (error != null) Notice(error!, error: true),
                if (message != null) Notice(message!),
                if (busy) const LinearProgressIndicator(),
                for (final key in session.pendingHistoricalAssetKeys)
                  card([
                    const Text(
                      'Die Antwort auf einen ursprünglichen Anlagenauftrag ist noch offen.',
                    ),
                    button(
                      'Ursprünglichen Anlagenauftrag unverändert erneut senden',
                      rights && !busy ? () => repeat(key) : null,
                    ),
                  ]),
                if (state != null) ...[
                  Text('Bestätigter Anlagenstand: ${state!['revision']}'),
                  if (state!['profile'] == null)
                    const Notice(
                      'Tatsächliches Buchführungsprofil und Übernahmestichtag fehlen. Es werden keine Unternehmenswerte vorgegeben.',
                    ),
                  if (state!['profile'] != null)
                    Text(
                      'Übernahmestichtag aus bestätigtem Profil: ${businessDate(state!['profile']['profile']['bookkeeping_start'])} · vor der ersten Tagesbewegung',
                    ),
                  if (state!['can_prepare'] != true)
                    const Notice(
                      'Neue Annahmen benötigen aktuelle Rechte, Finanzbetrieb und gegebenenfalls Wiederherstellungsabgleich.',
                    ),
                  if (writable && !pending)
                    button(
                      'Historische Anlage aus Originalen vorbereiten',
                      edit,
                    ),
                  if (choices.isNotEmpty)
                    DropdownButtonFormField<String>(
                      key: ValueKey('historical-selected-$selected'),
                      initialValue: choices.contains(selected)
                          ? selected
                          : null,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText:
                            'Vorhandene Inventaridentität oder Original wählen',
                      ),
                      items: [
                        for (final key in choices)
                          DropdownMenuItem(
                            value: key,
                            child: Text(key, overflow: TextOverflow.ellipsis),
                          ),
                      ],
                      onChanged: busy
                          ? null
                          : (v) {
                              setState(() => selected = v);
                              load();
                            },
                    ),
                  if (current != null) entryCard(current!),
                  if (selected != null && report != null) ...[
                    TextField(
                      controller: year,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'AfA-Auswertungsjahr',
                      ),
                    ),
                    button(
                      'Jahresquote und Buchungsstand prüfen',
                      busy ? null : load,
                    ),
                    if (annual != null)
                      card([
                        Text('Jahres-AfA ${report!['year']}'),
                        Text(
                          'Ursprüngliche Jahresquote: ${businessMoney(annual['continuation']['original_annual_depreciation'])}',
                        ),
                        Text(
                          'Bereits im Übernahmejahr gebucht: ${businessMoney(annual['continuation']['imported_current_year_depreciation'])}',
                        ),
                        Text(
                          'Verbleibende Jahres-AfA: ${businessMoney(annual['continuation']['amount'])}',
                        ),
                        Text(
                          annual['depreciation'] == null
                              ? 'Keine bestätigte Folge-AfA für dieses Jahr. Eine Nullquote braucht keine Scheinbuchung.'
                              : 'Folge-AfA im EÜR-Journal bestätigt.',
                        ),
                        if (businessEuerWritable(session) &&
                            current?['status'] == 'active')
                          button(
                            'Folge-AfA im EÜR-Journal prüfen',
                            busy ? null : () => euer(depreciation: true),
                          ),
                      ]),
                    button(
                      'EÜR-Journal, Gegenbuchungen und Perioden öffnen',
                      busy ? null : () => euer(),
                    ),
                  ],
                  if (editing && rights && !pending) ...[
                    card([
                      const Text(
                        'Nur tatsächlich belegte ursprüngliche Werte eingeben.',
                      ),
                      input('inventory_number', readOnly: sameSelectedDraft),
                      button(
                        'Inventarnummer eindeutig prüfen',
                        writable ? identify : null,
                      ),
                      if (draftKey != null)
                        Text('Bestätigte Inventaridentität: $draftKey'),
                      if (draftKey != null)
                        button(
                          'Historisches Anlagenoriginal hochladen',
                          writable ? upload : null,
                        ),
                    ]),
                    if (draftKey != null) ...[
                      DropdownButtonFormField<String>(
                        key: ValueKey('historical-original-$originalId'),
                        initialValue: originalId,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Unverändertes Anlagenoriginal ausdrücklich wählen',
                        ),
                        items: [
                          for (final o in businessItems(
                            state!['originals'],
                          ).where((v) => v['asset_key'] == draftKey))
                            DropdownMenuItem(
                              value: o['id'],
                              child: Text(
                                o['filename'],
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                        ],
                        onChanged: busy
                            ? null
                            : (v) => setState(() => originalId = v),
                      ),
                      if (originalId != null)
                        button(
                          'Ausgewähltes Anlagenoriginal öffnen',
                          busy
                              ? null
                              : () => original(
                                  businessItems(state!['originals'])
                                      .firstWhere((o) => o['id'] == originalId),
                                ),
                        ),
                      input('position'),
                      input('history_through'),
                      input('description'),
                      input('acquired_on'),
                      input('use_start'),
                      input('life_months'),
                      DropdownButtonFormField<String>(
                        key: ValueKey('historical-rounding-$rounding'),
                        initialValue: rounding.isEmpty ? null : rounding,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Tatsächlich belegtes bisheriges Rundungsverfahren',
                        ),
                        items: [
                          for (final r in historicalAssetRounding.entries)
                            DropdownMenuItem(
                              value: r.key,
                              child: Text(
                                r.value,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                        ],
                        onChanged: busy
                            ? null
                            : (v) => setState(() => rounding = v ?? ''),
                      ),
                      for (final k in _moneyFields) input(k),
                      input('account'),
                      CheckboxListTile(
                        value: confirmedHistory,
                        onChanged: busy
                            ? null
                            : (v) =>
                                  setState(() => confirmedHistory = v == true),
                        title: const Text(
                          'Originalwerte, ausschließlich betriebliche bewegliche Anlage und unveränderte lineare Historie einschließlich bisheriger Rundung ausdrücklich geprüft.',
                        ),
                      ),
                      input('reason'),
                      button(
                        'Anlagenvortrag unverbindlich prüfen',
                        writable ? () => prepare() : null,
                      ),
                      if (sameSelectedDraft && current?['status'] == 'active')
                        button(
                          'Unveränderten bisherigen Anlagenvortrag zur Aufhebung prüfen',
                          writable ? () => prepare(voiding: true) : null,
                        ),
                    ],
                  ],
                  if (preview != null && !pending)
                    card([
                      Text(
                        preview!['status'] == 'void'
                            ? 'Geprüfte Aufhebung'
                            : 'Geprüfte historische Übernahme',
                      ),
                      assetFacts(businessMap(preview!['asset'])),
                      Text(
                        'Originalposition: ${preview!['source']['position']}',
                      ),
                      Text(
                        'Verbleibende Startjahres-AfA: ${businessMoney(preview!['start_year']['amount'])}',
                      ),
                      const Notice(
                        'Diese Annahme bucht weder Geldfluss noch Vorsteuer oder neue Anschaffung. Eine Folge-AfA erfordert einen eigenen ausdrücklich geprüften EÜR-Auftrag.',
                      ),
                      CheckboxListTile(
                        value: accepted,
                        onChanged: busy
                            ? null
                            : (v) => setState(() => accepted = v == true),
                        title: const Text(
                          'Ich bestätige genau diese historische Anlage, Originalposition und Vortragswerte.',
                        ),
                      ),
                      button(
                        preview!['status'] == 'void'
                            ? 'Anlagenvortrag belegt aufheben'
                            : 'Geprüften Anlagenvortrag bestätigen',
                        writable && accepted ? confirm : null,
                      ),
                    ]),
                  if (selected != null) ...[
                    const Text('Unveränderte Anlagenhistorie'),
                    if (history.isEmpty)
                      const Text(
                        'Noch kein bestätigter Vortrag dieser Inventaridentität.',
                      ),
                    for (final old in history.reversed)
                      entryCard(old, historical: true),
                  ],
                ],
              ],
            ),
    );
  }
}

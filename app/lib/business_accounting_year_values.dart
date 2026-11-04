import 'dart:convert';
import 'dart:io';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting_year_values_contract.dart';
import 'business_accounting_open_items_contract.dart';
import 'business_accounting_openings_contract.dart';
import 'business_accounting_euer.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_widgets.dart';
export 'business_accounting_year_values_contract.dart';

class BusinessYearValuesPage extends StatefulWidget {
  const BusinessYearValuesPage({
    super.key,
    required this.session,
    this.pickFile,
    this.exportFile,
  });
  final BusinessSession session;
  final Future<XFile?> Function()? pickFile;
  final Future<void> Function(VerifiedMailAttachment)? exportFile;
  @override
  State<BusinessYearValuesPage> createState() => _BusinessYearValuesPageState();
}

class _BusinessYearValuesPageState extends State<BusinessYearValuesPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  final fields = <String, TextEditingController>{};
  Map<String, dynamic>? state, history, preview, body, editing, source;
  List<Map<String, dynamic>> openingItems = [],
      sources = [],
      controls = [],
      prior = [];
  String? year,
      mode,
      error,
      message,
      ledgerProof,
      selectedItem,
      sourceKind,
      invoiceProof,
      cutoverProof,
      vatProof,
      direction,
      rate,
      category;
  bool busy = false,
      denied = false,
      backgrounded = false,
      continuous = false,
      journalComplete = false,
      supported = false,
      scope = false,
      accepted = false;
  DialogRoute<bool>? ownedDialog;
  NavigatorState? dialogNavigator;
  void closeOwnedDialog() {
    final route = ownedDialog, nav = dialogNavigator;
    ownedDialog = null;
    dialogNavigator = null;
    if (route == null || nav == null) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (nav.mounted && route.isActive) nav.removeRoute(route);
    });
  }

  int epoch = 0;
  Object? generation;
  String? token, base;
  TextEditingController c(String key) =>
      fields.putIfAbsent(key, () => TextEditingController());
  bool get readable => yearValuesReadable(session) && !denied && !backgrounded;
  bool get mayReplay =>
      readable && yearValuesWritable(session) && !busy && session.error == null;
  bool get writable =>
      mayReplay &&
      (mode == 'void' ||
          state?['can_prepare'] == true && yearValuesConfigured(state));
  bool get pending => session.pendingYearValuesKeys.isNotEmpty;
  List<Map<String, dynamic>> get originals => state == null
      ? []
      : businessItems(state!['originals'])
            .where((o) => o['entity_key'] == year)
            .toList();
  Map<String, dynamic>? get current => state == null
      ? null
      : businessItems(state!['items'])
            .where((e) => e['entity_key'] == year)
            .firstOrNull;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    session.addListener(changed);
    bind();
    load();
  }

  void bind() {
    generation = session.generation;
    token = session.api.token;
    base = session.api.base;
  }

  void clearDraft() {
    closeOwnedDialog();
    for (final v in fields.values) {
      v.clear();
    }
    mode = null;
    editing = preview = body = null;
    sources = [];
    controls = [];
    clearSource();
    ledgerProof = null;
    continuous = journalComplete = supported = accepted = false;
  }

  void clearSource() {
    sourceKind = selectedItem = invoiceProof = cutoverProof = vatProof =
        direction = rate = category = null;
    prior = [];
    scope = false;
    for (final e in fields.entries.where((e) => e.key.startsWith('source:'))) {
      e.value.clear();
    }
  }

  void clear() {
    epoch++;
    state = history = source = null;
    openingItems = [];
    year = null;
    error = message = null;
    busy = false;
    clearDraft();
  }

  @override
  void didUpdateWidget(covariant BusinessYearValuesPage old) {
    super.didUpdateWidget(old);
    if (!identical(old.session, session)) {
      old.session.removeListener(changed);
      session.addListener(changed);
      clear();
      bind();
      load();
    }
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!yearValuesReadable(session) ||
          generation != session.generation ||
          token != session.api.token ||
          base != session.api.base) {
        clear();
        bind();
      } else if ((mode != null || busy) && !yearValuesWritable(session)) {
        epoch++;
        busy = false;
        clearDraft();
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState v) {
    if (!mounted) return;
    if ([
      AppLifecycleState.paused,
      AppLifecycleState.hidden,
      AppLifecycleState.detached,
    ].contains(v)) {
      setState(() {
        clear();
        backgrounded = denied = true;
      });
    } else if (v == AppLifecycleState.resumed) {
      setState(() => backgrounded = false);
    }
  }

  @override
  void dispose() {
    epoch++;
    closeOwnedDialog();
    WidgetsBinding.instance.removeObserver(this);
    session.removeListener(changed);
    for (final v in fields.values) {
      v.dispose();
    }
    super.dispose();
  }

  bool same(int stamp) =>
      mounted &&
      stamp == epoch &&
      !backgrounded &&
      yearValuesReadable(session) &&
      token == session.api.token &&
      base == session.api.base &&
      generation == session.generation;
  Future<bool> fresh(int stamp, {bool write = false}) async {
    await session.load();
    if (!same(stamp)) return false;
    if (session.error != null || session.loading)
      throw const ApiException(
        0,
        'Aktuelle Rechte konnten nicht bestätigt werden.',
      );
    if (write && !yearValuesWritable(session))
      throw const ApiException(
        403,
        'Aktuelle Schreibrechte für Jahresvorträge fehlen.',
      );
    return true;
  }

  void failed(Object e, int stamp) {
    if (!mounted || stamp != epoch) return;
    final deniedNow = e is ApiException && [401, 403, 404].contains(e.status);
    setState(() {
      if (deniedNow) {
        clear();
        denied = true;
      } else {
        error = e is ApiException
            ? e.message
            : e is FormatException
            ? e.message
            : 'Die Jahreswerte konnten nicht geprüft werden.';
      }
      busy = false;
    });
  }

  Future<void> load() async {
    if (backgrounded) return;
    final stamp = ++epoch;
    setState(() {
      busy = true;
      denied = false;
      error = null;
      state = history = source = null;
      clearDraft();
    });
    try {
      await session.load();
      if (!same(stamp)) return;
      final next = yearValuesState(await session.read(yearValuesPath));
      if (!await fresh(stamp)) return;
      for (final entry in businessItems(next['items'])) {
        await yearValuesVerifiedEntry(
          session,
          entry,
          stillCurrent: () => same(stamp),
        );
      }
      if (!await fresh(stamp)) return;
      final p = businessMap(next['profile']?['profile']);
      final y = p['bookkeeping_start'] is String
          ? (p['bookkeeping_start'] as String).substring(0, 4)
          : businessItems(next['items']).firstOrNull?['entity_key'];
      setState(() {
        state = next;
        year = y;
        busy = false;
      });
    } catch (e) {
      failed(e, stamp);
    } finally {
      if (mounted && stamp == epoch) setState(() => busy = false);
    }
  }

  Future<void> start({bool correction = false, bool voiding = false}) async {
    if ((voiding ? !mayReplay : !writable) || pending || year == null) return;
    final stamp = ++epoch;
    setState(() => busy = true);
    try {
      if (!await fresh(stamp, write: true)) return;
      final next = yearValuesState(await session.read(yearValuesPath));
      final old = businessItems(next['items'])
          .where((e) => e['entity_key'] == year)
          .firstOrNull;
      final items = openItemState(await session.read(openItemPath));
      if (!await fresh(stamp, write: true)) return;
      setState(() {
        state = next;
        clearDraft();
        mode = voiding ? 'void' : 'active';
        openingItems = businessItems(items['items'])
            .where(
              (e) =>
                  e['operation'] == 'item' &&
                  e['payload']['status'] == 'active',
            )
            .map((row) {
              final e = openItemCopy(row);
              for (final k in ['remaining', 'remaining_net', 'remaining_tax']) {
                e.remove(k);
              }
              return openItemEvent(e);
            })
            .toList();
        if (correction || voiding) {
          if (old == null)
            throw const ApiException(
              409,
              'Die ursprüngliche Jahresfassung fehlt.',
            );
          editing = openItemCopy(old);
          final p = old['payload'];
          sources = businessItems(
            openItemCopy({'items': p['sources']})['items'],
          );
          controls = businessItems(
            openItemCopy({'items': p['controls']})['items'],
          );
          c('from').text = p['coverage']['from'];
          c('through').text = p['coverage']['through'];
          ledgerProof = p['ledger_proof']['original_id'];
        }
        busy = false;
      });
    } catch (e) {
      failed(e, stamp);
    }
  }

  Map<String, dynamic> proof(String? id) {
    final original = originals.where((o) => o['id'] == id).firstOrNull;
    if (original == null)
      throw const FormatException(
        'Passendes ursprüngliches Jahresoriginal ausdrücklich wählen.',
      );
    return {'original_id': original['id'], 'sha256': original['sha256']};
  }

  String day(String key) => openingDate(c(key).text.trim());
  Map<String, dynamic> closedRecord() {
    final p = {
      'status': 'active',
      'currency': 'EUR',
      'external_system': openItemText(
        c('source:external_system').text,
        'Altsystem',
      ),
      'external_id': openItemText(
        c('source:external_id').text,
        'Alte Rechnungskennung',
      ),
      'direction': direction,
      'counterparty_key': openItemText(
        c('source:counterparty_key').text,
        'Gegenparteikennung',
      ),
      'counterparty_name': openItemText(
        c('source:counterparty_name').text,
        'Gegenpartei',
      ),
      'invoice_number': openItemText(
        c('source:invoice_number').text,
        'Rechnungsnummer',
      ),
      'invoice_date': day('source:invoice_date'),
      'service_date': day('source:service_date'),
      'invoice_received_date': day('source:invoice_received_date'),
      'history_through': day('source:history_through'),
      'rate': rate,
      'category': category,
      'net': openItemAmount(c('source:net').text),
      'tax': openItemAmount(c('source:tax').text),
      'gross': openItemAmount(c('source:gross').text),
      'invoice_proof': proof(invoiceProof),
      'cutover_proof': proof(cutoverProof),
      'prior_payments': prior,
      'prior_input_vat': direction == 'payable'
          ? {
              'amount': openItemAmount(c('source:vat_amount').text),
              'entitlement_date': day('source:vat_day'),
              'declared_period': c('source:vat_period').text.trim(),
              'deducted_on': day('source:deducted_on'),
              'proof': proof(vatProof),
            }
          : null,
      'scope_confirmed': scope,
    };
    yearValuesClosedRecord(p, businessMap(state!['profile']['profile']));
    return p;
  }

  Future<void> smallEditor(
    String title,
    List<BusinessField> fs,
    Future<void> Function(Map<String, dynamic>) apply,
  ) async {
    final stamp = epoch;
    if (!await fresh(stamp, write: true) || !mounted) return;
    final nav = Navigator.of(context, rootNavigator: true);
    final route = DialogRoute<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: title,
        fields: fs,
        readAllowed: () =>
            same(stamp) && mode != null && yearValuesWritable(session),
        saveLabel: 'Geprüfte Angaben übernehmen',
        onSave: (v) async {
          if (!await fresh(stamp, write: true))
            throw const ApiException(
              409,
              'Der Jahresvortragskontext wurde geändert.',
            );
          await apply(v);
          if (same(stamp)) setState(() {});
        },
      ),
    );
    closeOwnedDialog();
    ownedDialog = route;
    dialogNavigator = nav;
    try {
      await nav.push(route);
    } finally {
      if (identical(ownedDialog, route)) {
        ownedDialog = null;
        dialogNavigator = null;
      }
    }
  }

  BusinessField field(
    String name,
    String label, {
    BusinessInput type = BusinessInput.text,
    Map<String, String> choices = const {},
  }) =>
      BusinessField(name, label, type: type, choices: choices, required: true);
  Future<void> addPayment() => smallEditor(
    'Belegte frühere Zahlung',
    [
      field(
        'date',
        'Tatsächlicher alter Zahlungstag',
        type: BusinessInput.date,
      ),
      field('reference', 'Ursprüngliche Zahlungsreferenz'),
      field('gross', 'Belegtes Brutto', type: BusinessInput.decimal),
      field('net', 'Belegtes Netto', type: BusinessInput.decimal),
      field('tax', 'Belegter Steueranteil', type: BusinessInput.decimal),
      field(
        'proof',
        'Zahlungsoriginal',
        type: BusinessInput.choice,
        choices: {
          '': 'Bitte wählen',
          for (final o in originals)
            o['id']: '${o['filename']} · ${o['sha256'].substring(0, 12)}',
        },
      ),
    ],
    (v) async {
      prior.add({
        'date': v['date'],
        'reference': openItemText(v['reference'], 'Zahlungsreferenz'),
        'gross': openItemAmount(v['gross']),
        'net': openItemAmount(v['net']),
        'tax': openItemAmount(v['tax']),
        'proof': proof(v['proof']),
      });
    },
  );
  Future<void> addControl() => smallEditor(
    'Belegte Journal-Kontrollsumme',
    [
      field(
        'ledger',
        'Ursprüngliches Journal',
        type: BusinessInput.choice,
        choices: {'': 'Bitte wählen', 'euer': 'EÜR', 'vat': 'Umsatzsteuer'},
      ),
      field(
        'category',
        'Ursprüngliche Kategorie',
        type: BusinessInput.choice,
        choices: {'': 'Bitte wählen', ...euerCategories},
      ),
      field('account', 'Geprüftes ursprüngliches SKR04-Konto'),
      field(
        'amount',
        'Belegter vorzeichenbehafteter Betrag',
        type: BusinessInput.decimal,
      ),
    ],
    (v) async {
      controls.add({
        'ledger': v['ledger'],
        'category': v['category'],
        'account': yearValuesAccount(v['account']),
        'amount': yearValuesAmount(v['amount']),
      });
    },
  );
  Future<void> addSource() async {
    if (!writable) return;
    try {
      Map<String, dynamic> s, record;
      if (sourceKind == 'opening_item') {
        final old = openingItems
            .where((e) => e['id'] == selectedItem)
            .firstOrNull;
        if (old == null)
          throw const FormatException(
            'Unveränderte bestätigte Altpostenfassung wählen.',
          );
        record = businessMap(old['payload']);
        s = {
          'kind': 'opening_item',
          'entry_id': old['id'],
          'entry_hash': old['content_hash'],
        };
      } else if (sourceKind == 'closed_trade') {
        record = closedRecord();
        s = {'kind': 'closed_trade', 'record': record};
      } else {
        throw const FormatException('Ursprüngliche Quellenart wählen.');
      }
      final keys = c('source:cash_keys').text
          .split('\n')
          .map((v) => v.trim())
          .where((v) => v.isNotEmpty)
          .toList();
      if (keys.length != (record['prior_payments'] as List).length)
        throw const FormatException(
          'Für jede alte Zahlung genau eine ursprüngliche Buchungsidentität in derselben Reihenfolge eingeben.',
        );
      s.addAll({
        'accounts': {
          'net': yearValuesAccount(c('source:net_account').text.trim()),
          'tax': yearValuesAccount(c('source:tax_account').text.trim()),
          'input_vat': yearValuesAccount(c('source:input_account').text.trim()),
        },
        'cash_entry_keys': keys,
        'vat_entry_key': record['prior_input_vat'] == null
            ? null
            : openItemText(c('source:vat_key').text, 'Alte Vorsteuerbuchung'),
      });
      setState(() {
        sources.add(openItemCopy(s));
        clearSource();
        error = null;
      });
    } catch (e) {
      failed(e, epoch);
    }
  }

  Future<void> prepare() async {
    if (!writable || pending) return;
    final stamp = epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (!await fresh(stamp, write: true)) return;
      final next = yearValuesState(await session.read(yearValuesPath));
      if (!await fresh(stamp, write: true)) return;
      final payload = mode == 'void'
          ? openItemCopy(editing!['payload'])
          : {
              'status': 'active',
              'coverage': {'from': day('from'), 'through': day('through')},
              'sources': sources,
              'controls': controls,
              'ledger_proof': proof(ledgerProof),
              'attestations': {
                'continuous_method': continuous,
                'original_journal_complete': journalComplete,
                'no_unsupported_values': supported,
              },
            };
      if (mode == 'void') payload['status'] = 'void';
      final input = {
        'expected_revision': next['revision'],
        'state_hash': next['state_hash'],
        'entity_key': yearValuesYear(year),
        'profile_ref': mode == 'void'
            ? editing!['profile_ref']
            : next['profile_ref'],
        'operation': 'year_values',
        'payload': payload,
        'reason': openItemText(c('reason').text, 'Prüf-/Korrekturgrund', 1000),
      };
      final raw = await session.api.call(
        session.path('$yearValuesPath/preview'),
        input,
      );
      if (!await fresh(stamp, write: true)) return;
      final result = yearValuesPreview(
        raw,
        input,
        openingItems: mode == 'void' ? null : openingItems,
      );
      setState(() {
        state = next;
        body = openItemCopy(input);
        preview = result;
        accepted = false;
        busy = false;
      });
    } catch (e) {
      failed(e, stamp);
    } finally {
      if (same(stamp)) setState(() => busy = false);
    }
  }

  Future<void> confirm() async {
    if (!writable || preview == null || body == null || !accepted) return;
    final stamp = epoch,
        p = openItemCopy(preview),
        b = {
          ...openItemCopy(body),
          'preview_hash': preview!['preview_hash'],
          'confirmation': true,
        },
        s = openItemCopy(state),
        key = 'accounting-year-values-confirm-$year';
    setState(() => busy = true);
    try {
      await session.yearValuesCommand(
        key,
        '$yearValuesPath/confirm',
        b,
        validateResult: yearValuesReceipt(b, p, s),
        stillCurrent: () => same(stamp),
      );
      if (!await fresh(stamp)) return;
      await load();
      if (mounted)
        setState(
          () => message = 'Ursprüngliche Jahresfassung angenommen. Die gesonderte EÜR-Übernahme bleibt ausdrücklich zu prüfen.',
        );
    } catch (e) {
      failed(e, stamp);
    } finally {
      if (same(stamp)) setState(() => busy = false);
    }
  }

  Future<void> retry(String key) async {
    if (!mayReplay) return;
    final stamp = epoch;
    setState(() => busy = true);
    try {
      await session.repeatYearValuesCommand(
        key,
        stillCurrent: () => same(stamp),
      );
      if (!await fresh(stamp)) return;
      await load();
    } catch (e) {
      failed(e, stamp);
    } finally {
      if (same(stamp)) setState(() => busy = false);
    }
  }

  Future<void> upload() async {
    if (!writable || year == null || pending) return;
    final stamp = epoch;
    setState(() => busy = true);
    try {
      if (!await fresh(stamp, write: true)) return;
      final file =
          await (widget.pickFile?.call() ??
              openFile(
                acceptedTypeGroups: [
                  const XTypeGroup(
                    label: 'Originalnachweis',
                    extensions: ['pdf', 'png', 'jpg', 'jpeg'],
                  ),
                ],
              ));
      if (file == null || !await fresh(stamp, write: true)) return;
      final size = await file.length();
      if (size < 1 || size > 5242880)
        throw const FormatException(
          'Originaldatei zwischen 1 Byte und 5 MiB wählen.',
        );
      final bytes = await file.readAsBytes();
      if (bytes.length != size || bytes.isEmpty || bytes.length > 5242880)
        throw const FormatException(
          'Die Originaldatei wurde während des Lesens geändert oder überschreitet 5 MiB.',
        );
      if (!await fresh(stamp, write: true)) return;
      final ext = file.name.split('.').last.toLowerCase(),
          media = ext == 'pdf'
              ? 'application/pdf'
              : ext == 'png'
              ? 'image/png'
              : ['jpg', 'jpeg'].contains(ext)
              ? 'image/jpeg'
              : null;
      if (media == null)
        throw const FormatException('PDF, PNG oder JPEG erforderlich.');
      final input = {
        'entity_key': year,
        'filename': file.name,
        'media_type': media,
        'content_base64': base64Encode(bytes),
      };
      await session.yearValuesCommand(
        'accounting-year-values-original-$year',
        '$yearValuesPath/originals',
        input,
        validateResult: yearValuesUploadReceipt(input, bytes),
        stillCurrent: () => same(stamp),
      );
      if (!await fresh(stamp)) return;
      final next = yearValuesState(await session.read(yearValuesPath));
      if (!await fresh(stamp)) return;
      setState(() => state = next);
    } catch (e) {
      failed(e, stamp);
    } finally {
      if (same(stamp)) setState(() => busy = false);
    }
  }

  Future<void> download(Map<String, dynamic> raw) async {
    final stamp = epoch;
    try {
      if (!await fresh(stamp)) return;
      final original = yearValuesOriginal(raw),
          bytes = await session.api.bytes(
            session.path(original['path']),
            mediaType: original['media_type'],
            maxBytes: 5242880,
          );
      if (!await fresh(stamp)) return;
      if (bytes.length != original['size'] ||
          openingDigest(bytes) != original['sha256'])
        throw const ApiException(
          0,
          'Originalbytes stimmen nicht mit Größe und SHA-256 überein.',
        );
      final file = VerifiedMailAttachment(
        bytes: bytes,
        filename: original['filename'],
        mediaType: original['media_type'],
        sha256: original['sha256'],
      );
      if (widget.exportFile != null) {
        await widget.exportFile!(file);
      } else if (Platform.isLinux || Platform.isMacOS || Platform.isWindows) {
        final location = await getSaveLocation(suggestedName: file.filename);
        if (location == null || !await fresh(stamp)) return;
        // A chooser may outlive silent server-side permission changes. Read the
        // same protected original again before writing, never merely old bytes.
        final latest = await session.api.bytes(
          session.path(original['path']),
          mediaType: original['media_type'],
          maxBytes: 5242880,
        );
        if (!await fresh(stamp)) return;
        if (latest.length != original['size'] ||
            openingDigest(latest) != original['sha256'])
          throw const ApiException(
            0,
            'Das ursprüngliche Dokument wurde nach der Dateiauswahl verändert.',
          );
        await File(location.path).writeAsBytes(latest, flush: true);
      } else if (mounted) {
        await exportMailAttachment(context, file, () => same(stamp));
      }
    } catch (e) {
      failed(e, stamp);
    }
  }

  Future<void> showHistory() async {
    if (!readable || year == null) return;
    final stamp = ++epoch;
    setState(() {
      busy = true;
      history = source = null;
      clearDraft();
    });
    try {
      if (!await fresh(stamp)) return;
      final value = yearValuesHistory(
        await session.read('$yearValuesPath/history?entity_key=$year'),
        year!,
      );
      if (!await fresh(stamp)) return;
      for (final entry in businessItems(value['items'])) {
        await yearValuesVerifiedEntry(
          session,
          entry,
          stillCurrent: () => same(stamp),
        );
      }
      if (!await fresh(stamp)) return;
      setState(() => history = value);
    } catch (e) {
      failed(e, stamp);
    } finally {
      if (same(stamp)) setState(() => busy = false);
    }
  }

  Future<void> showSource(Map<String, dynamic> entry) async {
    final stamp = epoch;
    try {
      if (!await fresh(stamp)) return;
      await yearValuesVerifiedEntry(
        session,
        entry,
        stillCurrent: () => same(stamp),
      );
      final value = yearValuesSource(
        await session.read(
          '$yearValuesPath/years/${entry['entity_key']}?revision=${entry['revision']}',
        ),
        entry: entry,
      );
      if (!await fresh(stamp)) return;
      setState(() => source = value);
    } catch (e) {
      failed(e, stamp);
    }
  }

  void openEuer() {
    if (!readable) return;
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) =>
            BusinessEuerPage(session: session, initialYearValuesYear: year),
      ),
    );
  }

  Widget input(String key, String label, {bool multiline = false}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: TextField(
      key: ValueKey('year-values-$key'),
      controller: c(key),
      enabled: writable && preview == null && mode != 'void',
      maxLines: multiline ? 3 : 1,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    ),
  );
  Widget choice(
    String label,
    String? value,
    Map<String, String> options,
    void Function(String?) changed,
  ) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: DropdownButtonFormField<String>(
      key: ValueKey('$label:$value:${options.keys.join(',')}'),
      initialValue: options.containsKey(value) ? value : null,
      isExpanded: true,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      items: options.entries
          .map(
            (e) => DropdownMenuItem(
              value: e.key,
              child: Text(
                e.value,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          )
          .toList(),
      onChanged: writable && preview == null && mode != 'void'
          ? (v) => setState(() => changed(v))
          : null,
    ),
  );
  Widget originalChoice(
    String label,
    String? value,
    void Function(String?) changed,
  ) => choice(label, value, {
    for (final o in originals)
      o['id']: '${o['filename']} · ${o['sha256'].substring(0, 12)}',
  }, changed);
  Widget toggle(String label, bool value, void Function(bool) changed) =>
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        title: Text(label),
        value: value,
        onChanged: writable && preview == null && mode != 'void'
            ? (v) => setState(() => changed(v == true))
            : null,
      );
  Widget details(Map<String, dynamic> d) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        'Belegter Zeitraum ${businessDate(d['coverage']['from'])} bis ${businessDate(d['coverage']['through'])}',
      ),
      Text(
        d['complete_prior_period'] == true
            ? 'Erklärte Deckung des gesamten Zeitraums vor Softwarebeginn'
            : 'Teilzeitraum: kein vollständiges Unternehmensjahr',
      ),
      for (final p in businessItems(d['historical_postings']))
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(
            '${p['ledger'] == 'euer' ? 'EÜR' : 'Umsatzsteuer'} · ${euerCategories[p['category']] ?? p['category']} · ${p['account']}',
          ),
          subtitle: Text(
            '${businessDate(p['date'])} · ${p['original_entry_key']}',
          ),
          trailing: Text(businessMoney(p['amount'])),
        ),
      for (final v in businessItems(
        d['copied_rows'],
      ).where((r) => r['kind'] == 'already_exercised_input_vat'))
        Text(
          'Bereits ausgeübte Vorsteuer ${businessMoney(v['amount'])} · Anspruch ${businessDate(v['date'])} · ausgeübt ${businessDate(v['deducted_on'])} · ursprünglicher Zeitraum ${v['declared_period']}',
        ),
    ],
  );
  Widget sourceEditor() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      choice(
        'Ursprüngliche Quellenart',
        sourceKind,
        {
          'opening_item': 'Bestätigte Altpostenfassung',
          'closed_trade': 'Vollständig erledigte externe Rechnung',
        },
        (v) {
          clearSource();
          sourceKind = v;
        },
      ),
      if (sourceKind == 'opening_item')
        choice('Unveränderte Altpostenfassung', selectedItem, {
          for (final e in openingItems)
            e['id']:
                '${e['payload']['invoice_number']} · ${e['payload']['counterparty_name']} · Fassung ${e['revision']}',
        }, (v) => selectedItem = v),
      if (sourceKind == 'closed_trade') ...[
        const Notice(yearValuesScope),
        choice('Rechnungsrichtung', direction, {
          'receivable': 'Kundenforderung',
          'payable': 'Lieferantenverbindlichkeit',
        }, (v) => direction = v),
        for (final e in {
          'external_system': 'Ursprüngliches Buchführungssystem',
          'external_id': 'Ursprüngliche Rechnungskennung',
          'counterparty_key': 'Ursprüngliche Gegenparteikennung',
          'counterparty_name': 'Gegenpartei',
          'invoice_number': 'Ursprüngliche Rechnungsnummer',
          'invoice_date': 'Rechnungsdatum (JJJJ-MM-TT)',
          'service_date': 'Leistungsdatum (JJJJ-MM-TT)',
          'invoice_received_date': 'Rechnungseingang (JJJJ-MM-TT)',
          'history_through': 'Belegte Historie bis (JJJJ-MM-TT)',
          'net': 'Ursprüngliches Netto',
          'tax': 'Ursprüngliche Steuer',
          'gross': 'Ursprüngliches Brutto',
        }.entries)
          input('source:${e.key}', e.value),
        choice('Belegter Steuersatz', rate, {
          '19': '19 %',
          '7': '7 %',
        }, (v) => rate = v),
        choice(
          'Gewöhnliche Kategorie',
          category,
          openItemCategories,
          (v) => category = v,
        ),
        originalChoice(
          'Rechnungsoriginal',
          invoiceProof,
          (v) => invoiceProof = v,
        ),
        originalChoice(
          'Original der vollständig erledigten Historie',
          cutoverProof,
          (v) => cutoverProof = v,
        ),
        for (var i = 0; i < prior.length; i++)
          ListTile(
            title: Text(
              '${businessDate(prior[i]['date'])} · ${businessMoney(prior[i]['gross'])}',
            ),
            subtitle: Text(prior[i]['reference']),
            trailing: IconButton(
              onPressed: writable
                  ? () => setState(() => prior.removeAt(i))
                  : null,
              icon: const Icon(Icons.remove_circle_outline),
            ),
          ),
        TextButton(
          onPressed: writable ? addPayment : null,
          child: const Text('Frühere tatsächliche Zahlung hinzufügen'),
        ),
        if (direction == 'payable') ...[
          for (final e in {
            'vat_amount': 'Früher tatsächlich abgezogene Vorsteuer',
            'vat_day': 'Ursprünglicher Anspruchstag (JJJJ-MM-TT)',
            'vat_period': 'Ursprünglich erklärter Zeitraum (JJJJ-MM)',
            'deducted_on': 'Tatsächlicher Ausübungstag (JJJJ-MM-TT)',
          }.entries)
            input('source:${e.key}', e.value),
          originalChoice(
            'Original des früheren Vorsteuerabzugs',
            vatProof,
            (v) => vatProof = v,
          ),
        ],
        toggle(
          'Gewöhnlichen vollständig betrieblichen Rechnungsumfang ausdrücklich geprüft',
          scope,
          (v) => scope = v,
        ),
      ],
      if (sourceKind != null) ...[
        input('source:net_account', 'Ursprüngliches SKR04-Nettokonto'),
        input('source:tax_account', 'Ursprüngliches SKR04-Steuerkonto'),
        input('source:input_account', 'Ursprüngliches SKR04-Vorsteuerkonto'),
        input(
          'source:cash_keys',
          'Alte Zahlungsbuchungen: eine Kennung je Zahlung in Originalreihenfolge',
          multiline: true,
        ),
        input(
          'source:vat_key',
          'Ursprüngliche Vorsteuerbuchungsidentität (nur Lieferantenrechnung)',
        ),
        TextButton(
          onPressed: writable ? addSource : null,
          child: const Text('Geprüfte ursprüngliche Quelle hinzufügen'),
        ),
      ],
    ],
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Belegte Jahresvorträge')),
    body: !readable
        ? Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                const Notice(
                  'Jahreswerte sind in diesem aktuellen Kontext nicht verfügbar.',
                ),
                TextButton(
                  onPressed: backgrounded ? null : load,
                  child: const Text('Aktuelle Rechte und Bestand neu prüfen'),
                ),
              ],
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const Notice(yearValuesScope),
              const Notice(yearValuesBoundary),
              if (busy) const LinearProgressIndicator(),
              if (error != null) Notice(error!),
              if (message != null) Notice(message!),
              if (state != null) ...[
                Text(
                  'Bestätigter Softwarebeginn: ${businessDate(state!['profile']?['profile']?['bookkeeping_start'])}',
                ),
                if (!yearValuesConfigured(state))
                  const Notice(
                    'Bestätigtes unterstütztes Buchführungsprofil erforderlich.',
                  ),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    TextButton(
                      onPressed: busy ? null : load,
                      child: const Text('Neu laden'),
                    ),
                    TextButton(
                      onPressed: busy ? null : showHistory,
                      child: const Text('Ursprüngliche Jahresfassungen'),
                    ),
                    TextButton(
                      onPressed: openEuer,
                      child: const Text(
                        'EÜR, Gegenbuchungen und Perioden prüfen',
                      ),
                    ),
                    TextButton(
                      onPressed: writable && !pending ? upload : null,
                      child: const Text('Jahresoriginal hochladen'),
                    ),
                  ],
                ),
                for (final key in session.pendingYearValuesKeys)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Unbekannte Antwort: ursprünglicher Auftrag bleibt offen',
                          ),
                          Text(
                            key.contains('-original-')
                                ? 'Originalannahme unverändert prüfen'
                                : 'Jahresannahme unverändert prüfen',
                          ),
                          TextButton(
                            onPressed: mayReplay ? () => retry(key) : null,
                            child: const Text('Unverändert erneut prüfen'),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (current != null)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Jahr ${current!['entity_key']} · Fassung ${current!['revision']} · ${current!['payload']['status'] == 'active' ? 'Aktiv' : 'Aufgehoben'}',
                          ),
                          details(businessMap(current!['details'])),
                          SelectableText(
                            'Originalhash ${current!['content_hash']}',
                          ),
                          Wrap(
                            spacing: 8,
                            children: [
                              TextButton(
                                onPressed: writable && !pending
                                    ? () => start(correction: true)
                                    : null,
                                child: const Text(
                                  'Belegte Korrektur vorbereiten',
                                ),
                              ),
                              TextButton(
                                onPressed:
                                    mayReplay &&
                                        !pending &&
                                        current!['payload']['status'] ==
                                            'active'
                                    ? () => start(voiding: true)
                                    : null,
                                child: const Text('Unverändert aufheben'),
                              ),
                              TextButton(
                                onPressed: () => showSource(current!),
                                child: const Text(
                                  'Gebundene Jahresquelle prüfen',
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                if (mode == null)
                  TextButton(
                    onPressed: writable && !pending ? () => start() : null,
                    child: const Text('Jahresvortrag vorbereiten'),
                  ),
                ExpansionTile(
                  key: PageStorageKey('year-originals:$year'),
                  title: Text(
                    'Geschützte Jahresoriginale (${originals.length})',
                  ),
                  children: [
                    for (final o in originals)
                      ListTile(
                        title: Text(o['filename']),
                        subtitle: Text('${o['size']} Byte · ${o['sha256']}'),
                        onTap: () => download(o),
                      ),
                  ],
                ),
                if (mode != null) ...[
                  Text(
                    mode == 'void'
                        ? 'Unveränderte ursprüngliche Jahresfassung aufheben'
                        : 'Ursprüngliche Jahresangaben ausdrücklich prüfen',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  if (mode != 'void') ...[
                    input('from', 'Belegter Zeitraum von (JJJJ-MM-TT)'),
                    input('through', 'Belegter Zeitraum bis (JJJJ-MM-TT)'),
                    originalChoice(
                      'Eigenständiges Zeitraumjournal',
                      ledgerProof,
                      (v) => ledgerProof = v,
                    ),
                    for (var i = 0; i < sources.length; i++)
                      ListTile(
                        title: Text(
                          sources[i]['kind'] == 'opening_item'
                              ? 'Gebundene Altpostenfassung'
                              : 'Vollständig erledigter externer Beleg',
                        ),
                        subtitle: Text(
                          '${sources[i]['cash_entry_keys'].length} ursprüngliche Zahlungen · ${sources[i]['accounts']}',
                        ),
                        trailing: IconButton(
                          onPressed: writable && preview == null
                              ? () => setState(() => sources.removeAt(i))
                              : null,
                          icon: const Icon(Icons.remove_circle_outline),
                        ),
                      ),
                    if (preview == null) sourceEditor(),
                    for (var i = 0; i < controls.length; i++)
                      ListTile(
                        title: Text(
                          '${controls[i]['ledger']} · ${euerCategories[controls[i]['category']] ?? controls[i]['category']} · ${controls[i]['account']}',
                        ),
                        subtitle: Text(businessMoney(controls[i]['amount'])),
                        trailing: IconButton(
                          onPressed: writable && preview == null
                              ? () => setState(() => controls.removeAt(i))
                              : null,
                          icon: const Icon(Icons.remove_circle_outline),
                        ),
                      ),
                    TextButton(
                      onPressed: writable && preview == null
                          ? addControl
                          : null,
                      child: const Text('Belegte Kontrollsumme hinzufügen'),
                    ),
                    toggle(
                      'Buchführungsmethode unverändert fortgeführt',
                      continuous,
                      (v) => continuous = v,
                    ),
                    toggle(
                      'Ursprüngliches Journal im erklärten Zeitraum vollständig geprüft',
                      journalComplete,
                      (v) => journalComplete = v,
                    ),
                    toggle(
                      'Keine unzulässigen Anlagen-, Lohn-, Privat- oder Sonderwerte enthalten',
                      supported,
                      (v) => supported = v,
                    ),
                  ],
                  if (mode == 'void')
                    const Notice(
                      'Vor der Aufhebung aktive EÜR-Übernahme gegenbuchen und betroffene gesperrte Perioden ausdrücklich öffnen. Die alte Fassung bleibt unverändert erhalten.',
                    ),
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: TextField(
                      key: const ValueKey('year-values-reason'),
                      controller: c('reason'),
                      enabled: writable && preview == null,
                      decoration: const InputDecoration(
                        labelText: 'Prüf-/Korrekturgrund',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                  if (preview == null)
                    FilledButton(
                      onPressed: writable && !pending ? prepare : null,
                      child: const Text('Originale und Jahreswerte vorprüfen'),
                    ),
                  if (preview != null) ...[
                    details(businessMap(preview!['details'])),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text(
                        'Genau diese ursprünglichen Werte und Nachweise verbindlich bestätigen',
                      ),
                      value: accepted,
                      onChanged: writable
                          ? (v) => setState(() => accepted = v == true)
                          : null,
                    ),
                    FilledButton(
                      onPressed: writable && accepted && !pending
                          ? confirm
                          : null,
                      child: const Text('Geprüfte Jahresfassung annehmen'),
                    ),
                  ],
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => setState(() {
                            epoch++;
                            clearDraft();
                          }),
                    child: const Text('Bearbeitung schließen'),
                  ),
                ],
                if (history != null)
                  for (final e in businessItems(history!['items']))
                    ExpansionTile(
                      key: PageStorageKey('year-values-history:${e['id']}'),
                      title: Text(
                        'Ursprüngliche Fassung ${e['revision']} · ${e['payload']['status'] == 'active' ? 'Aktiv' : 'Aufgehoben'}',
                      ),
                      children: [
                        details(businessMap(e['details'])),
                        SelectableText(
                          e['content_hash'],
                          key: PageStorageKey('year-history-hash:${e['id']}'),
                        ),
                        TextButton(
                          onPressed: () => showSource(e),
                          child: const Text(
                            'Diese ursprüngliche Quelle prüfen',
                          ),
                        ),
                        for (final p in businessItems(e['proofs']))
                          ListTile(
                            title: Text(p['filename']),
                            subtitle: Text(p['sha256']),
                            onTap: () => download(p),
                          ),
                      ],
                    ),
                if (source != null)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Originalgebundene Jahres-/EÜR-Quelle'),
                          SelectableText(source!['source_hash']),
                          details(businessMap(source!['details'])),
                          const Notice(
                            'Keine Geldbewegung und kein neuer Vorsteueranspruch. Die EÜR-Übernahme ist ein gesonderter ausdrücklich bestätigter Vorgang.',
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ],
          ),
  );
}

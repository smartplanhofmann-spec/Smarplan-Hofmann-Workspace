import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_accounting.dart'
    show accountingCashDate, businessAccountingReadable;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

bool businessPreparationProfileReadable(BusinessSession session) =>
    businessAccountingReadable(session) &&
    session.hasFeature('accounting_preparation_profile') &&
    session.hasModule('accounting_profile');

const _profilePath = '/accounting/profile';
const _profileConfirm = '$_profilePath/confirm';
const _profileKey = 'accounting-profile';
const _regimes = {
  '': 'Unbekannt',
  'small_business': 'Kleinunternehmerregelung',
  'regular': 'Regelbesteuerung',
};
const _timings = {
  '': 'Unbekannt',
  'accrual': 'Sollbesteuerung',
  'cash': 'Istbesteuerung',
};

class BusinessPreparationProfilePage extends StatefulWidget {
  const BusinessPreparationProfilePage({super.key, required this.session});
  final BusinessSession session;
  @override
  State<BusinessPreparationProfilePage> createState() =>
      _BusinessPreparationProfilePageState();
}

class _BusinessPreparationProfilePageState
    extends State<BusinessPreparationProfilePage> {
  final reason = TextEditingController(),
      evidence = TextEditingController(),
      vatDate = TextEditingController(),
      bookkeepingDate = TextEditingController();
  final scroll = ScrollController();
  Map<String, dynamic>? state, preview, confirmBody;
  List<Map<String, dynamic>> history = [];
  int? nextHistory;
  int epoch = 0;
  bool loading = false,
      busy = false,
      denied = false,
      editing = false,
      accepted = false,
      vatDateKnown = false,
      bookkeepingDateKnown = false;
  String regime = '', timing = '';
  String? error, message;
  bool get pending => widget.session.pending(_profileKey);
  bool get mayRead =>
      businessPreparationProfileReadable(widget.session) && !denied;
  bool get writeRights =>
      mayRead &&
      widget.session.canWrite('accounting.admin') &&
      widget.session.sectionEnabled('finance');
  bool get mayWrite =>
      writeRights &&
      state?['writes_allowed'] == true &&
      widget.session.error == null &&
      !loading &&
      !busy;

  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    for (final controller in [reason, evidence, vatDate, bookkeepingDate]) {
      controller.dispose();
    }
    scroll.dispose();
    super.dispose();
  }

  void clearEditor() {
    editing = accepted = vatDateKnown = bookkeepingDateKnown = false;
    regime = timing = '';
    preview = confirmBody = null;
    for (final controller in [reason, evidence, vatDate, bookkeepingDate]) {
      controller.clear();
    }
  }

  void clear() {
    epoch++;
    state = null;
    history = [];
    nextHistory = null;
    loading = busy = false;
    clearEditor();
  }

  void changed() {
    if (!mounted) return;
    setState(() {
      if (!businessPreparationProfileReadable(widget.session)) {
        clear();
      } else if (!writeRights) {
        clearEditor();
      }
    });
  }

  void failure(Object value) {
    if (!mounted) return;
    setState(() {
      if (value is ApiException && [401, 403, 404].contains(value.status)) {
        clear();
        denied = true;
      }
      error = value is ApiException
          ? value.message
          : value is FormatException
          ? value.message
          : 'Das Vorbereitungsprofil konnte nicht geladen werden.';
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && scroll.hasClients) scroll.jumpTo(0);
    });
  }

  String? pendingFingerprint() {
    final path = widget.session.pendingPreparationProfilePath();
    return path == null
        ? null
        : jsonEncode(
            widget.session.pendingCommandValues(_profileKey, path: path),
          );
  }

  Future<void> load() async {
    if (!businessPreparationProfileReadable(widget.session)) return;
    final current = ++epoch, opening = pendingFingerprint();
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final values = await Future.wait([
        widget.session.read(_profilePath),
        widget.session.read('$_profilePath/history?limit=50&offset=0'),
      ]);
      if (!mounted ||
          current != epoch ||
          !businessPreparationProfileReadable(widget.session))
        return;
      if (opening != pendingFingerprint()) {
        await load();
        return;
      }
      setState(() {
        denied = false;
        state = businessMap(values[0]);
        history = businessItems(values[1]);
        nextHistory = businessMap(values[1])['next_offset'] as int?;
        clearEditor();
      });
    } catch (value) {
      if (mounted && current == epoch) failure(value);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<void> moreHistory() async {
    if (!mayRead || loading || busy || nextHistory == null) return;
    final current = ++epoch, offset = nextHistory!;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final result = businessMap(
        await widget.session.read(
          '$_profilePath/history?limit=50&offset=$offset',
        ),
      );
      if (!mounted || current != epoch || !mayRead) return;
      setState(() {
        history = [...history, ...businessItems(result)];
        nextHistory = result['next_offset'] as int?;
      });
    } catch (value) {
      if (mounted && current == epoch) failure(value);
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  void edit() {
    if (!mayWrite || pending) return;
    final profile = businessMap(
      businessMap(state!['current'] ?? {})['profile'] ?? {},
    );
    setState(() {
      clearEditor();
      regime = '${profile['vat_regime'] ?? ''}';
      timing = '${profile['vat_timing'] ?? ''}';
      vatDateKnown = profile['vat_effective_from'] != null;
      bookkeepingDateKnown = profile['bookkeeping_start'] != null;
      vatDate.text = '${profile['vat_effective_from'] ?? ''}';
      bookkeepingDate.text = '${profile['bookkeeping_start'] ?? ''}';
      editing = true;
      error = message = null;
    });
  }

  String requiredText(
    TextEditingController controller,
    String label,
    int maximum,
  ) {
    final value = controller.text;
    if (value.trim().isEmpty ||
        value.runes.length > maximum ||
        value.runes.any(
          (rune) =>
              rune < 32 || rune == 127 || (rune >= 0xd800 && rune <= 0xdfff),
        )) {
      throw FormatException(
        'Bitte $label einzeilig mit 1 bis $maximum Zeichen angeben.',
      );
    }
    return value;
  }

  String? date(TextEditingController controller, bool known, String label) {
    if (!known) return null;
    try {
      final value = accountingCashDate(controller.text);
      final year = int.parse(value.substring(0, 4));
      if (year < 1900 || year > 2200) throw const FormatException();
      return value;
    } on FormatException {
      throw FormatException(
        'Bitte für $label einen gültigen Kalendertag zwischen 1900 und 2200 angeben oder die Angabe unbekannt lassen.',
      );
    }
  }

  Future<void> freshWrite() async {
    await widget.session.load();
    if (widget.session.error != null || widget.session.loading) {
      throw const ApiException(
        0,
        'Die aktuellen Berechtigungen konnten noch nicht bestätigt werden.',
      );
    }
    if (!writeRights)
      throw const ApiException(
        403,
        'Die aktuelle Berechtigung zur Profilpflege fehlt.',
      );
    final fresh = businessMap(await widget.session.read(_profilePath));
    if (!writeRights)
      throw const ApiException(403, 'Die aktuelle Berechtigung fehlt.');
    if (fresh['writes_allowed'] != true)
      throw const ApiException(423, 'Neue Profilstände sind derzeit gesperrt.');
  }

  Future<void> prepare() async {
    if (!mayWrite || !editing || pending) return;
    final current = epoch;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      final body = <String, dynamic>{
        'expected_revision': state!['revision'],
        'state_hash': state!['state_hash'],
        'profile': {
          'legal_form': 'sole_proprietorship',
          'accounting_method': 'euer',
          'vat_regime': regime.isEmpty ? null : regime,
          'vat_timing': regime == 'regular' && timing.isNotEmpty
              ? timing
              : null,
          'vat_effective_from': date(
            vatDate,
            regime.isNotEmpty && vatDateKnown,
            'den Beginn der Umsatzsteuerangabe',
          ),
          'bookkeeping_start': date(
            bookkeepingDate,
            bookkeepingDateKnown,
            'den Buchführungsbeginn',
          ),
        },
        'reason': requiredText(reason, 'eine Begründung', 1000),
        'evidence_reference': requiredText(
          evidence,
          'eine Nachweisreferenz',
          200,
        ),
      };
      await freshWrite();
      if (!mounted || current != epoch || !writeRights || pending) return;
      final proposal = businessMap(
        await widget.session.previewPreparationProfile(body),
      );
      if (!mounted || current != epoch || !writeRights || pending) return;
      setState(() {
        preview = proposal;
        confirmBody = {
          ...body,
          'preview_hash': proposal['preview_hash'],
          'confirmation': true,
        };
        accepted = false;
      });
    } catch (value) {
      if (mounted && current == epoch) failure(value);
    } finally {
      if (mounted && current == epoch) setState(() => busy = false);
    }
  }

  Future<void> confirm({bool retry = false}) async {
    if (!mayWrite ||
        (retry ? !pending : pending || confirmBody == null || !accepted))
      return;
    final current = epoch, body = confirmBody;
    setState(() {
      busy = true;
      error = message = null;
    });
    try {
      if (retry) {
        await widget.session.repeatPreparationProfileCommand();
      } else {
        await freshWrite();
        if (!mounted || current != epoch || !writeRights || pending) return;
        await widget.session.command(_profileKey, _profileConfirm, body!);
      }
      if (!mounted || current != epoch || !mayRead) return;
      await load();
      if (mounted && mayRead)
        setState(
          () => message = 'Vorbereitungsstand gespeichert. Die steuerliche Einordnung bleibt offen.',
        );
    } catch (value) {
      if (mounted && current == epoch) {
        setState(clearEditor);
        failure(value);
        if (mayRead &&
            !pending &&
            value is ApiException &&
            value.status == 409) {
          final originalError = error;
          await load();
          if (mounted && mayRead) setState(() => error = originalError);
        }
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget heading(String value) =>
      Text(value, style: Theme.of(context).textTheme.titleMedium);
  Widget card(List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final child in children)
            Padding(padding: const EdgeInsets.only(bottom: 8), child: child),
        ],
      ),
    ),
  );
  List<Widget> profileDetails(Map<String, dynamic> profile) => [
    const Text('Unternehmensform: Einzelunternehmen'),
    const Text('Buchführungsform: Einnahmenüberschussrechnung (EÜR)'),
    Text(
      'Umsatzsteuer: ${_regimes[profile['vat_regime'] ?? ''] ?? 'Unbekannt'}',
    ),
    Text(
      'Soll-/Istbesteuerung: ${_timings[profile['vat_timing'] ?? ''] ?? 'Unbekannt'}',
    ),
    Text(
      'Beginn der Umsatzsteuerangabe: ${profile['vat_effective_from'] == null ? 'Unbekannt' : businessDate(profile['vat_effective_from'])}',
    ),
    Text(
      'Buchführungsbeginn: ${profile['bookkeeping_start'] == null ? 'Unbekannt' : businessDate(profile['bookkeeping_start'])}',
    ),
  ];
  Widget entry(
    Map<String, dynamic> value, {
    bool proposed = false,
    bool current = false,
  }) => card([
    heading(
      proposed
          ? 'Vorbereitungsstand prüfen'
          : '${current ? 'Aktueller Vorbereitungsstand' : 'Gespeicherter Vorbereitungsstand'} · Version ${value['revision']}',
    ),
    ...profileDetails(businessMap(value['profile'])),
    Text('Begründung: ${value['reason']}'),
    Text('Nachweisreferenz: ${value['evidence_reference']}'),
    const Text(
      'Diese Angaben aktivieren keine Steuerregel. Ein EÜR- oder Steuerergebnis ist weiterhin nicht verfügbar.',
    ),
    if (!proposed)
      Text('Gespeichert: ${businessDate(value['created_at'], time: true)}'),
    if (proposed) ...[
      CheckboxListTile(
        key: const ValueKey('profile-confirmation'),
        contentPadding: EdgeInsets.zero,
        controlAffinity: ListTileControlAffinity.leading,
        value: accepted,
        onChanged: mayWrite
            ? (value) => setState(() => accepted = value == true)
            : null,
        title: const Text(
          'Ich bestätige diese Angaben einschließlich der noch unbekannten Punkte als neuen Vorbereitungsstand.',
        ),
      ),
      FilledButton(
        onPressed: mayWrite && accepted ? () => confirm() : null,
        child: const Text('Vorbereitungsstand verbindlich speichern'),
      ),
      TextButton(
        onPressed: mayWrite
            ? () => setState(() {
                preview = confirmBody = null;
                accepted = false;
              })
            : null,
        child: const Text('Angaben ändern'),
      ),
    ],
  ]);
  Widget choice(
    String name,
    String label,
    String value,
    Map<String, String> options,
    void Function(String) onChange, {
    bool enabled = true,
  }) => DropdownButtonFormField<String>(
    key: ValueKey('profile-$name-$value'),
    initialValue: value,
    decoration: InputDecoration(labelText: label),
    isExpanded: true,
    items: options.entries
        .map(
          (entry) =>
              DropdownMenuItem(value: entry.key, child: Text(entry.value)),
        )
        .toList(),
    onChanged: mayWrite && enabled ? (value) => onChange(value ?? '') : null,
  );
  Widget dateInput(
    String name,
    String label,
    TextEditingController controller,
  ) => TextField(
    key: ValueKey('profile-$name'),
    controller: controller,
    enabled: mayWrite,
    decoration: InputDecoration(
      labelText: label,
      hintText: 'TT.MM.JJJJ oder JJJJ-MM-TT',
    ),
  );
  Widget editor() => card([
    heading('Neuen Vorbereitungsstand festhalten'),
    const Text(
      'Vorgeschlagene Grundlage: Einzelunternehmen mit Einnahmenüberschussrechnung (EÜR). Gespeichert wird erst nach Ihrer Vorschau und ausdrücklichen Bestätigung.',
    ),
    const Text(
      'Ungeklärte Angaben dürfen unbekannt bleiben. Es wird keine Istbesteuerung und kein Beginn aus vorhandenen Belegen abgeleitet.',
    ),
    choice(
      'vat-regime',
      'Umsatzsteuerangabe',
      regime,
      _regimes,
      (value) => setState(() {
        regime = value;
        if (value != 'regular') timing = '';
        if (value.isEmpty) {
          vatDateKnown = false;
          vatDate.clear();
        }
      }),
    ),
    choice(
      'vat-timing',
      'Soll-/Istbesteuerung',
      timing,
      _timings,
      (value) => setState(() => timing = value),
      enabled: regime == 'regular',
    ),
    SwitchListTile(
      key: const ValueKey('profile-vat-date-known'),
      contentPadding: EdgeInsets.zero,
      title: const Text('Beginn der Umsatzsteuerangabe ist bekannt'),
      subtitle: const Text('Ohne Angabe bleibt der Beginn unbekannt.'),
      value: vatDateKnown,
      onChanged: mayWrite && regime.isNotEmpty
          ? (value) => setState(() {
              vatDateKnown = value;
              if (!value) vatDate.clear();
            })
          : null,
    ),
    if (vatDateKnown)
      dateInput('vat-date', 'Beginn der Umsatzsteuerangabe', vatDate),
    SwitchListTile(
      key: const ValueKey('profile-bookkeeping-date-known'),
      contentPadding: EdgeInsets.zero,
      title: const Text('Buchführungsbeginn ist bekannt'),
      subtitle: const Text(
        'Dieser erklärte Beginn steuert noch keine Steuerperiode.',
      ),
      value: bookkeepingDateKnown,
      onChanged: mayWrite
          ? (value) => setState(() {
              bookkeepingDateKnown = value;
              if (!value) bookkeepingDate.clear();
            })
          : null,
    ),
    if (bookkeepingDateKnown)
      dateInput('bookkeeping-date', 'Buchführungsbeginn', bookkeepingDate),
    TextField(
      key: const ValueKey('profile-reason'),
      controller: reason,
      enabled: mayWrite,
      decoration: const InputDecoration(
        labelText: 'Begründung des Vorbereitungsstands',
      ),
    ),
    TextField(
      key: const ValueKey('profile-evidence'),
      controller: evidence,
      enabled: mayWrite,
      decoration: const InputDecoration(
        labelText: 'Nachweisreferenz',
        helperText: 'Zum Beispiel eine ausdrücklich bestätigte Inhaberangabe. Es wird kein Behördenbeleg geprüft oder abgerufen.',
        helperMaxLines: 3,
      ),
    ),
    OutlinedButton(
      onPressed: mayWrite ? prepare : null,
      child: const Text('Vorbereitungsstand vorschauen'),
    ),
    TextButton(
      onPressed: mayWrite ? () => setState(clearEditor) : null,
      child: const Text('Bearbeitung schließen'),
    ),
  ]);
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Vorbereitungsprofil'),
      actions: [
        IconButton(
          tooltip: 'Vorbereitungsprofil aktualisieren',
          onPressed: loading || busy ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !mayRead
        ? BusinessEmpty(
            'Vorbereitungsprofil nicht freigegeben',
            error ?? 'Globale Finanz- und EÜR-Leserechte sowie die Serverfreigabe sind erforderlich.',
          )
        : ListView(
            controller: scroll,
            padding: const EdgeInsets.all(24),
            children: [
              const Notice(
                'Hier werden ausdrücklich erklärte Grundlagen der EÜR-Vorbereitung festgehalten. Auch ein unvollständiger Stand darf gespeichert werden. Geldflüsse und steuerliche Einordnung bleiben unverändert.',
              ),
              if (error != null) Notice(error!, error: true),
              if (message != null) Notice(message!),
              if (loading || busy) const LinearProgressIndicator(),
              if (state != null) ...[
                if (state!['current'] == null)
                  card([
                    heading('Noch kein Vorbereitungsstand gespeichert'),
                    const Text(
                      'Einzelunternehmen und EÜR sind erst ein ungespeicherter Vorschlag. Umsatzsteuer, Soll-/Istbesteuerung und Beginn bleiben unbekannt.',
                    ),
                  ])
                else
                  entry(businessMap(state!['current']), current: true),
                if (!writeRights || state!['writes_allowed'] != true)
                  const Notice(
                    'Gespeicherte Vorbereitungsstände bleiben lesbar. Neue Versionen sind derzeit nicht freigegeben.',
                  ),
                if (pending)
                  card([
                    heading('Unbestätigter Vorbereitungsstand'),
                    const Text(
                      'Die frühere Übertragung wird zuerst unverändert wiederholt. Gespeicherte Eingaben bleiben bis zur aktuellen Prüfung verborgen.',
                    ),
                    FilledButton(
                      onPressed:
                          mayWrite &&
                              widget.session.pendingPreparationProfilePath() !=
                                  null
                          ? () => confirm(retry: true)
                          : null,
                      child: const Text('Unverändert erneut senden'),
                    ),
                  ])
                else if (preview != null)
                  entry(preview!, proposed: true)
                else if (editing)
                  editor()
                else if (mayWrite)
                  OutlinedButton(
                    onPressed: edit,
                    child: const Text('Neuen Vorbereitungsstand erfassen'),
                  ),
                const SizedBox(height: 16),
                heading('Historie der Vorbereitungsstände'),
                if (!loading && history.isEmpty)
                  const Text('Keine gespeicherten Versionen vorhanden.'),
                for (final value in history) entry(value),
                if (nextHistory != null)
                  OutlinedButton(
                    onPressed: loading || busy ? null : moreHistory,
                    child: const Text('Weitere Profilversionen laden'),
                  ),
              ],
            ],
          ),
  );
}

import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_payroll_wage_interruption_contract.dart';
export 'business_payroll_wage_interruption_contract.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

Map<String, dynamic> _copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
Never _fail(String message, [int status = 400]) =>
    throw ApiException(status, message);

bool payrollWageInterruptionsReadable(BusinessSession session) =>
    session.allowed &&
    session.projectId == null &&
    session.hasFeature('payroll_wage_interruptions') &&
    session.hasModule('payroll_wage_interruptions') &&
    session.can('personnel.read');

class PayrollWageInterruptionPlanView extends StatelessWidget {
  const PayrollWageInterruptionPlanView({super.key, required this.plan});
  final Map<String, dynamic> plan;
  @override
  Widget build(BuildContext context) {
    final value = payrollWageInterruptionPlan(plan);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value['can_determine'] == true
              ? 'Anzahl U: ${value['number_u']}'
              : 'Anzahl U noch ungeklärt',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        Text(
          'Prüfung bis ${businessDate(value['assessment_through'])} · ${businessItems(value['input']['days']).length} belegte Kalendertage',
        ),
        for (final b in businessItems(value['blockers']))
          Notice('${b['message']}'),
        for (final period in businessItems(value['periods']))
          ListTile(
            dense: true,
            title: Text(
              '${businessDate(period['from_date'])} bis ${businessDate(period['to_date'])}',
            ),
            subtitle: Text(
              '${period['workday_count']} aufeinanderfolgende vertragliche Arbeitstage ohne Entgeltanspruch · ein Unterbrechungszeitraum',
            ),
          ),
        if (value['can_determine'] == true &&
            (value['periods'] as List).isEmpty)
          const Text(
            'Geprüft: Im belegten Zeitraum liegt keine einzutragende Unterbrechung vor.',
          ),
        ExpansionTile(
          title: const Text('Abgeleitete Tagesherleitung'),
          children: [
            for (final d in businessItems(value['input']['days']))
              ListTile(
                dense: true,
                title: Text(
                  '${businessDate(d['date'])} · ${d['contractual_workday'] == true ? 'Vertraglicher Arbeitstag' : 'Planmäßig arbeitsfrei'}',
                ),
                subtitle: Text(
                  '${const {'none': 'Entgeltanspruch vollständig weggefallen', 'preserved': 'Entgeltanspruch erhalten', 'partial_unknown': 'Anspruch noch nicht vollständig beurteilt'}[d['wage_claim']]}\n${d['section41_1_4_payment_kind'] == 'none' ? 'Gesetzliche Ausnahmeleistungen geprüft: keine' : payrollWageInterruptionExceptions[d['section41_1_4_payment_kind']] ?? 'Gesetzliche Ausnahmeleistungen noch ungeklärt'}',
                ),
              ),
          ],
        ),
        const Notice(
          'Tage und Anzahl werden aus den tatsächlichen Lohnläufen, Anspruchsnachweisen und Arbeitsplänen abgeleitet. Dieser Jahresprüfstand löst keine Zahlung oder amtliche Übermittlung aus.',
          error: false,
        ),
      ],
    );
  }
}

class BusinessPayrollWageInterruptionsPage extends StatefulWidget {
  const BusinessPayrollWageInterruptionsPage({
    super.key,
    required this.session,
    required this.employee,
    required this.onOriginal,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final Future<void> Function(Map<String, dynamic>) onOriginal;
  @override
  State<BusinessPayrollWageInterruptionsPage> createState() =>
      _BusinessPayrollWageInterruptionsPageState();
}

class _BusinessPayrollWageInterruptionsPageState
    extends State<BusinessPayrollWageInterruptionsPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get commandKey => 'payroll-wage-interruptions-$employeeId';
  static const path = '/payroll/wage-interruptions';
  Map<String, dynamic>? sources,
      selected,
      draft,
      preview,
      previewBody,
      correction;
  List<Map<String, dynamic>> history = [];
  String? error;
  bool loading = false, busy = false, historical = false;
  Object? generation;
  BuildContext? editorContext;
  int epoch = 0;
  bool get readable => payrollWageInterruptionsReadable(session);
  bool get permitted =>
      readable && !session.readonly && session.can('personnel.approve');
  bool get writable =>
      permitted &&
      session.sectionEnabled('personnel') &&
      sources?['writes_enabled'] == true &&
      sources?['can_approve'] == true;
  Map<String, dynamic>? get pending =>
      session.pendingCommandValues(commandKey, path: path);
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didUpdateWidget(
    covariant BusinessPayrollWageInterruptionsPage oldWidget,
  ) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, session) ||
        oldWidget.employee['id'] != employeeId) {
      oldWidget.session.removeListener(changed);
      session.addListener(changed);
      epoch++;
      clear();
      generation = null;
      error = null;
      load();
    }
  }

  void clear() {
    final privateEditor = editorContext;
    editorContext = null;
    if (privateEditor != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (privateEditor.mounted &&
            ModalRoute.of(privateEditor)?.isCurrent == true) {
          Navigator.of(privateEditor).pop();
        }
      });
    }
    sources = selected = draft = preview = previewBody = correction = null;
    history = [];
    loading = false;
  }

  void changed() {
    if (mounted &&
        (!readable ||
            (draft != null || preview != null || editorContext != null) &&
                !permitted ||
            generation != null && generation != session.generation)) {
      epoch++;
      setState(() {
        clear();
        generation = session.generation;
      });
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused) {
      epoch++;
      if (mounted) setState(clear);
    }
  }

  void failed(Object e) {
    if (!mounted) return;
    setState(() {
      error = e is ApiException
          ? e.message
          : e is FormatException
          ? e.message
          : 'Der Jahresprüfstand konnte nicht abgeschlossen werden.';
      if (e is ApiException && [401, 403, 404].contains(e.status)) clear();
    });
  }

  Future<Map<String, dynamic>> fresh({
    bool write = false,
    bool replay = false,
  }) async {
    await session.load();
    if (!mounted || !readable || session.error != null || write && !permitted)
      _fail('Aktuelle globale Personal-Lese- und Freigaberechte fehlen.', 403);
    final stamp = session.generation,
        value = payrollWageInterruptionSources(
          await session.read('$path/sources?employee_id=$employeeId&year=2026'),
          employeeId,
        );
    if (!mounted ||
        !readable ||
        stamp != session.generation ||
        write && (!permitted || value['can_approve'] != true))
      _fail('Die private Mitarbeiterfreigabe wurde geändert.', 403);
    if (write &&
        !replay &&
        (!session.sectionEnabled('personnel') ||
            value['writes_enabled'] != true))
      _fail(
        'Neue U-Nachweise sind im pausierten Personalbereich gesperrt.',
        423,
      );
    return value;
  }

  Future<void> load() async {
    if (loading) return;
    final captured = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await fresh();
      if (mounted && captured == epoch)
        setState(() {
          sources = value;
          generation = session.generation;
        });
    } catch (e) {
      if (captured == epoch) failed(e);
    } finally {
      if (mounted && captured == epoch) setState(() => loading = false);
    }
  }

  Future<void> act(Future<void> Function() run) async {
    if (busy) return;
    final captured = epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await run();
    } catch (e) {
      if (mounted && readable && captured == epoch) failed(e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> inspect(Map<String, dynamic> raw, {bool old = false}) async {
    final captured = epoch;
    final record = payrollWageInterruptionRecord(raw, employeeId),
        page = await fresh();
    if (mounted && readable && captured == epoch)
      setState(() {
        sources = page;
        generation = session.generation;
        selected = _copy(record);
        historical = old;
        draft = preview = previewBody = correction = null;
        history = [];
      });
  }

  Future<void> repeat() => act(() async {
    final captured = epoch;
    final result = await session.repeatPayrollWageInterruptionsCommand(
      employeeId,
    );
    if (mounted && readable && captured == epoch)
      await inspect(businessMap(result));
  });
  Future<void> save(
    Map<String, dynamic> body, {
    Map<String, dynamic>? previous,
    Map<String, dynamic>? proof,
  }) async {
    final captured = epoch;
    await fresh(write: true);
    if (pending != null)
      _fail('Zuerst den ursprünglichen unbestätigten Auftrag klären.', 409);
    final result = payrollWageInterruptionRecord(
      await session.command(
        commandKey,
        path,
        body,
        validateResult: payrollWageInterruptionValidator(
          body,
          previous: previous,
          preview: proof,
        ),
      ),
      employeeId,
    );
    if (mounted && readable && captured == epoch) await inspect(result);
  }

  Map<String, String> choices(
    dynamic rows,
    String Function(Map<String, dynamic>) label,
  ) => {for (final v in businessItems(rows)) '${v['id']}': label(v)};
  Future<Map<String, dynamic>?> choose(
    String title,
    List<BusinessField> fields, {
    Map<String, dynamic> initial = const {},
  }) async {
    Map<String, dynamic>? result;
    final captured = epoch;
    await showDialog<bool>(
      context: context,
      builder: (dialog) {
        editorContext = dialog;
        return BusinessEditor(
          session: session,
          title: title,
          fields: fields,
          initial: initial,
          readPermission: 'personnel.read',
          writePermission: 'personnel.approve',
          readAllowed: () => readable && captured == epoch,
          saveLabel: 'Geprüfte Angaben übernehmen',
          onSave: (values) async {
            await fresh(write: true);
            result = _copy(values);
          },
        );
      },
    );
    editorContext = null;
    return mounted && readable && captured == epoch ? result : null;
  }

  List<dynamic> ids(dynamic refs) =>
      businessItems(refs ?? []).map((v) => v['id']).toList();
  Map<String, dynamic> valuesFrom(Map<String, dynamic>? prior) {
    final d = businessMap(prior?['details']);
    return {
      'year': 2026,
      'assessment_through': d['assessment_through'],
      'employment_terms_ids': ids(d['employment_terms_refs']),
      'run_ids': ids(d['run_refs']),
      'work_schedule_ids': ids(d['work_schedule_refs']),
      'entitlement_case_ids': ids(d['entitlement_case_refs']),
      'exception_review_file_ids': ids(d['exception_review_file_refs']),
      'source_file_ids': prior?['source_file_ids'] ?? [],
      'excluded_reviews': {},
      'excluded_payments': businessItems(d['excluded_payments'] ?? [])
          .map(
            (p) => {
              'from': p['from'],
              'to': p['to'],
              'kind': p['kind'],
              'evidence_file_ids': ids(p['evidence_refs']),
            },
          )
          .toList(),
      'verification_note': d['verification_note'] ?? '',
      'correction_reason': '',
    };
  }

  Future<void> editSources([Map<String, dynamic>? prior]) async {
    if (busy || pending != null) return;
    final captured = epoch;
    try {
      final page = await fresh(write: true);
      if (!mounted || captured != epoch) return;
      final existing = prior ?? correction,
          values = draft == null ? valuesFrom(existing) : _copy(draft!);
      BusinessField multi(
        String name,
        String label,
        dynamic rows,
        String Function(Map<String, dynamic>) labeler, {
        bool required = false,
      }) => BusinessField(
        name,
        label,
        type: BusinessInput.multiple,
        required: required,
        choices: choices(rows, labeler),
        initial: values[name],
      );
      final result = await choose('Quellen für die Jahresprüfung auswählen', [
        BusinessField(
          'assessment_through',
          'Tatsächlich geprüft bis',
          type: BusinessInput.date,
          required: true,
          initial: values['assessment_through'],
        ),
        multi(
          'employment_terms_ids',
          'Alle belegten Beschäftigungsepisoden',
          businessItems(page['facts'])
              .where(
                (v) =>
                    v['kind'] == 'employment_terms' && v['status'] == 'active',
              )
              .toList(),
          (v) =>
              'Ab ${businessDate(v['effective_from'])} · Fassung ${v['revision']}',
          required: true,
        ),
        multi(
          'run_ids',
          'Tatsächliche angenommene Lohnläufe',
          page['runs'],
          (v) => '${v['source']['month']} · Fassung ${v['revision']}',
        ),
        multi(
          'work_schedule_ids',
          'Vollständige datierte Arbeitspläne',
          businessItems(page['facts'])
              .where(
                (v) => v['kind'] == 'work_schedule' && v['status'] == 'active',
              )
              .toList(),
          (v) => '${v['details']['month']} · Fassung ${v['revision']}',
        ),
        multi(
          'entitlement_case_ids',
          'Einschlägige Krankheits- und Unterbrechungsnachweise',
          businessItems(page['entitlements'])
              .where((v) => v['status'] == 'active')
              .toList(),
          (v) =>
              '${businessDate(v['effective_from'])} · Fassung ${v['revision']}',
        ),
        multi(
          'exception_review_file_ids',
          'Originale für die Prüfung aller gesetzlichen Ausnahmeleistungen',
          page['files'],
          (v) => '${v['filename']}',
          required: true,
        ),
        multi(
          'source_file_ids',
          'Geschützte Originale der Jahresprüfung',
          page['files'],
          (v) => '${v['filename']}',
          required: true,
        ),
        BusinessField(
          'verification_note',
          'Beurteilung der gesetzlichen Unterbrechungsaufzeichnung',
          type: BusinessInput.multiline,
          required: true,
          initial: values['verification_note'],
        ),
        if (existing != null)
          BusinessField(
            'correction_reason',
            'Belegter Korrekturgrund',
            type: BusinessInput.multiline,
            required: true,
            initial: values['correction_reason'],
          ),
      ]);
      if (result != null && mounted)
        setState(() {
          sources = page;
          generation = session.generation;
          draft = {...values, ...result, 'year': 2026, 'excluded_reviews': {}};
          correction = existing == null ? null : _copy(existing);
          selected = preview = previewBody = null;
          history = [];
          historical = false;
        });
    } catch (e) {
      if (captured == epoch) failed(e);
    }
  }

  Future<void> reviewPayments() async {
    if (draft == null || busy) return;
    final localEpoch = epoch;
    final captured = _copy(draft!);
    try {
      final results = await choose('Jede gesetzliche Leistungsart prüfen', [
        for (final e in payrollWageInterruptionExceptions.entries)
          BusinessField(
            e.key,
            e.value,
            type: BusinessInput.choice,
            required: true,
            initial: captured['excluded_reviews']?[e.key] ?? '',
            choices: const {
              '': 'Bitte ausdrücklich prüfen',
              'none': 'Nicht vorhanden – anhand der Originale geprüft',
              'present': 'Vorhanden – Zeitraum und Originale werden gebunden',
            },
          ),
      ]);
      if (results != null && mounted && draft != null)
        setState(() {
          draft!['excluded_reviews'] = results;
          preview = previewBody = null;
        });
    } catch (e) {
      if (localEpoch == epoch) failed(e);
    }
  }

  Future<void> addPayment() async {
    if (draft == null || busy) return;
    final localEpoch = epoch;
    try {
      final page = await fresh(write: true);
      if (!mounted || localEpoch != epoch) return;
      final value = await choose('Belegten Ausnahmezeitraum ergänzen', [
        BusinessField(
          'kind',
          'Gesetzliche Leistungsart',
          type: BusinessInput.choice,
          required: true,
          choices: {
            '': 'Bitte auswählen',
            ...payrollWageInterruptionExceptions,
          },
        ),
        const BusinessField(
          'from',
          'Tatsächlicher Beginn',
          type: BusinessInput.date,
          required: true,
        ),
        const BusinessField(
          'to',
          'Tatsächliches Ende',
          type: BusinessInput.date,
          required: true,
        ),
        BusinessField(
          'evidence_file_ids',
          'Konkrete geschützte Originale',
          type: BusinessInput.multiple,
          required: true,
          choices: choices(page['files'], (v) => '${v['filename']}'),
        ),
      ]);
      if (value != null && mounted && draft != null)
        setState(() {
          draft!['excluded_payments'] = [
            ...businessItems(draft!['excluded_payments']),
            value,
          ];
          draft!['excluded_reviews'] = {};
          preview = previewBody = null;
        });
    } catch (e) {
      if (localEpoch == epoch) failed(e);
    }
  }

  Future<void> prepare() => act(() async {
    if (draft == null || pending != null) return;
    final localEpoch = epoch;
    final page = await fresh(write: true), captured = session.generation;
    final body = payrollWageInterruptionInput(
      employeeId,
      page,
      _copy(draft!),
      previous: correction,
    );
    final proof = payrollWageInterruptionPreview(
      await session.api.call(
        session.path('$path/preview'),
        payrollWageInterruptionPreviewInput(body),
      ),
      body,
    );
    if (mounted &&
        readable &&
        localEpoch == epoch &&
        captured == session.generation)
      setState(() {
        sources = page;
        preview = proof;
        previewBody = {...body, 'preview_hash': proof['preview_hash']};
        selected = null;
        history = [];
      });
  });
  Future<void> confirm() async {
    if (preview == null || previewBody == null || !writable || pending != null)
      return;
    final proof = _copy(preview!),
        body = _copy(previewBody!),
        old = correction == null ? null : _copy(correction!);
    if (!await businessConfirm(
      context,
      title: 'Geprüften Jahresstand festhalten',
      message: 'Ich bestätige genau diesen Jahresprüfstand und seine gebundenen Originale. Eine ungeklärte Anzahl bleibt ausdrücklich ungeklärt.',
      action: 'Jahresprüfstand festhalten',
    ))
      return;
    await act(() => save(body, previous: old, proof: proof));
  }

  Future<void> cancel(Map<String, dynamic> fact) async {
    if (pending != null) return;
    final localEpoch = epoch;
    try {
      await fresh(write: true);
      if (!mounted || localEpoch != epoch) return;
      final values = await choose(
        'Fälschlichen Jahresprüfstand aufheben',
        const [
          BusinessField(
            'correction_reason',
            'Belegter Aufhebungsgrund',
            type: BusinessInput.multiline,
            required: true,
          ),
          BusinessField(
            'confirmed',
            'Ich bestätige die Aufhebung; frühere Fassungen bleiben unverändert.',
            type: BusinessInput.toggle,
          ),
        ],
      );
      if (values == null) return;
      if (values['confirmed'] != true)
        _fail('Die Aufhebung ausdrücklich bestätigen.');
      await act(() async {
        final page = await fresh(write: true);
        await save({
          'employee_id': employeeId,
          'employee_revision': page['employee']['revision'],
          'kind': payrollWageInterruptionKind,
          'rule_version': payrollWageInterruptionRule,
          'source_contract_version': 1,
          'id': fact['id'],
          'revision': fact['revision'],
          'status': 'void',
          'details': _copy(fact['details']),
          'source_file_ids': List.from(fact['source_file_ids']),
          'preview_hash': fact['preview_hash'],
          'correction_reason': values['correction_reason'],
          'confirmed': true,
        }, previous: fact);
      });
    } catch (e) {
      if (localEpoch == epoch) failed(e);
    }
  }

  Future<void> showHistory(Map<String, dynamic> fact) => act(() async {
    await fresh();
    final captured = epoch,
        result = businessMap(await session.read('$path/${fact['id']}/history')),
        items = businessItems(result['items']);
    if (result['items'] is! List ||
        items.indexed.any(
          (entry) =>
              payrollWageInterruptionRecord(entry.$2, employeeId)['id'] !=
                  fact['id'] ||
              entry.$2['revision'] != entry.$1 + 1,
        ))
      _fail('Die Jahresprüfhistorie gehört nicht zum gewählten Nachweis.');
    if (mounted && readable && captured == epoch)
      setState(() => history = items);
  });
  Widget originals(dynamic files) => Wrap(
    spacing: 8,
    children: [
      for (final file in businessItems(files))
        TextButton(
          onPressed: busy
              ? null
              : () => act(() async {
                  final captured = epoch;
                  await fresh();
                  if (mounted && readable && captured == epoch)
                    await widget.onOriginal(file);
                }),
          child: Text('Original: ${file['filename']}'),
        ),
    ],
  );
  Widget recordView(Map<String, dynamic> value) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Jahresprüfstand 2026 · Fassung ${value['revision']}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text(
            value['status'] == 'void'
                ? 'Aufgehoben; historische Fassung bleibt erhalten.'
                : 'Aktiver Jahresprüfstand',
          ),
          Text('${value['details']['verification_note']}'),
          if ('${value['correction_reason'] ?? ''}'.isNotEmpty)
            Text('Korrekturgrund: ${value['correction_reason']}'),
          PayrollWageInterruptionPlanView(plan: businessMap(value['plan'])),
          originals(value['sources']['source_files']),
          if (!historical)
            OutlinedButton(
              onPressed: busy ? null : () => showHistory(value),
              child: const Text('Jahresprüfhistorie öffnen'),
            ),
          if (!historical && writable && pending == null)
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton(
                  onPressed: busy ? null : () => editSources(value),
                  child: const Text('Jahresprüfstand korrigieren'),
                ),
                if (value['status'] == 'active')
                  OutlinedButton(
                    onPressed: busy ? null : () => cancel(value),
                    child: const Text('Fälschlichen Jahresprüfstand aufheben'),
                  ),
              ],
            ),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final drafts = businessItems(draft?['excluded_payments'] ?? []);
    return Scaffold(
      appBar: AppBar(title: const Text('Unterbrechungen im Lohnkonto')),
      body: !readable
          ? const Center(
              child: Text('Keine aktuelle globale Personalfreigabe.'),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  '${widget.employee['name'] ?? 'Mitarbeiter'} · Prüfjahr 2026',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                if (error != null) Notice(error!),
                if (loading) const LinearProgressIndicator(),
                if (!loading && sources == null)
                  OutlinedButton(
                    onPressed: load,
                    child: const Text('Jahresquellen neu laden'),
                  ),
                if (pending != null)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Ein ursprünglicher Auftrag ist noch unbestätigt. Vor weiteren Änderungen seine Annahme prüfen.',
                          ),
                          OutlinedButton(
                            onPressed: busy || !permitted ? null : repeat,
                            child: const Text(
                              'Ursprünglichen Auftrag erneut prüfen',
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (sources != null &&
                    pending == null &&
                    writable &&
                    businessItems(sources!['assessments']).isEmpty &&
                    draft == null)
                  OutlinedButton(
                    onPressed: busy ? null : () => editSources(),
                    child: const Text('Jahresprüfung vorbereiten'),
                  ),
                if (sources != null)
                  for (final value in businessItems(sources!['assessments']))
                    ListTile(
                      title: Text(
                        'Jahresprüfstand · Fassung ${value['revision']}',
                      ),
                      subtitle: Text(
                        value['status'] == 'void'
                            ? 'Aufgehoben'
                            : value['plan']['can_determine'] == true
                            ? 'Anzahl U: ${value['plan']['number_u']}'
                            : 'Anzahl U noch ungeklärt',
                      ),
                      onTap: busy ? null : () => act(() => inspect(value)),
                    ),
                if (draft != null) ...[
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Privater Entwurf bis ${businessDate(draft!['assessment_through'])}',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          Text('${draft!['verification_note']}'),
                          Text(
                            '${businessItems(draft!['excluded_payments']).length} belegte Ausnahmezeiträume · ${businessMap(draft!['excluded_reviews']).length}/${payrollWageInterruptionExceptions.length} Leistungsarten geprüft',
                          ),
                          if (writable && pending == null)
                            Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: [
                                OutlinedButton(
                                  onPressed: busy ? null : () => editSources(),
                                  child: const Text('Quellenauswahl ändern'),
                                ),
                                OutlinedButton(
                                  onPressed: busy ? null : addPayment,
                                  child: const Text(
                                    'Ausnahmezeitraum ergänzen',
                                  ),
                                ),
                                OutlinedButton(
                                  onPressed: busy ? null : reviewPayments,
                                  child: const Text(
                                    'Alle gesetzlichen Leistungsarten prüfen',
                                  ),
                                ),
                              ],
                            ),
                          for (final entry in drafts.indexed)
                            ListTile(
                              title: Text(
                                payrollWageInterruptionExceptions[entry
                                        .$2['kind']] ??
                                    'Leistungsart',
                              ),
                              subtitle: Text(
                                '${businessDate(entry.$2['from'])} bis ${businessDate(entry.$2['to'])}',
                              ),
                              trailing: IconButton(
                                tooltip:
                                    'Ausnahmezeitraum aus Entwurf entfernen',
                                icon: const Icon(Icons.delete_outline),
                                onPressed: busy || !writable || pending != null
                                    ? null
                                    : () => setState(() {
                                        draft!['excluded_payments'] = drafts
                                            .indexed
                                            .where((p) => p.$1 != entry.$1)
                                            .map((p) => p.$2)
                                            .toList();
                                        draft!['excluded_reviews'] = {};
                                        preview = previewBody = null;
                                      }),
                              ),
                            ),
                          if (writable && pending == null)
                            FilledButton(
                              onPressed: busy ? null : prepare,
                              child: const Text(
                                'Jahresprüfung unverbindlich ableiten',
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ],
                if (preview != null)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Unverbindlicher Jahresprüfstand'),
                          PayrollWageInterruptionPlanView(
                            plan: businessMap(preview!['plan']),
                          ),
                          originals(
                            preview!['source_snapshot']['source_files'],
                          ),
                          if (writable &&
                              pending == null &&
                              preview!['can_confirm'] == true)
                            FilledButton(
                              onPressed: busy ? null : confirm,
                              child: const Text(
                                'Geprüften Jahresstand festhalten',
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                if (selected != null) recordView(selected!),
                for (final value in history)
                  ListTile(
                    title: Text('Historische Fassung ${value['revision']}'),
                    subtitle: Text(
                      businessDate(value['created_at'], time: true),
                    ),
                    onTap: busy
                        ? null
                        : () => act(() => inspect(value, old: true)),
                  ),
              ],
            ),
    );
  }
}

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_oneoff_case_contract.dart';
export 'business_payroll_oneoff_case_contract.dart';
import 'business_payroll_annual_basis_contract.dart' show payrollAnnualBranches;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Never _fail(String message, [int status = 400]) =>
    throw ApiException(status, message);
String _money(dynamic value) => value is int
    ? businessMoney(
        '${value ~/ 100}.${(value.abs() % 100).toString().padLeft(2, '0')}',
      )
    : 'Nicht berechenbar';
bool payrollOneoffCasesReadable(BusinessSession session) =>
    session.allowed &&
    session.projectId == null &&
    session.hasFeature('payroll_oneoff_cases') &&
    session.hasModule('payroll_oneoff_cases') &&
    session.can('personnel.read');

class PayrollOneoffCasePlanView extends StatelessWidget {
  const PayrollOneoffCasePlanView({super.key, required this.plan});
  final Map<String, dynamic> plan;
  Widget line(String title, String value) =>
      ListTile(dense: true, title: Text(title), subtitle: Text(value));
  @override
  Widget build(BuildContext context) {
    final detail = businessMap(plan['one_off_details']),
        running = businessMap(plan['running_calculation']),
        assignment = businessMap(detail['assignment']),
        social = businessMap(detail['social']),
        tax = businessMap(detail['tax']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        line('Lohnmonat', '${plan['month']}'),
        line('Laufendes Originalbrutto', _money(running['gross_minor'])),
        line('Einmaliger Bruttoanspruch', _money(detail['amount_minor'])),
        line('Geplanter Zuflusstag', businessDate(detail['receipt_date'])),
        line('Gesamtbrutto', _money(plan['gross_minor'])),
        if (assignment.isNotEmpty) ...[
          line(
            'SV-Zuordnung',
            const {
                  'march_clause': 'Märzklausel: tatsächliche Vorjahresperiode',
                  'current_year_last_period':
                      'Letzte tatsächliche Periode im laufenden Jahr',
                  'no_contributory_current_year_period':
                      'Keine beitragspflichtige laufende Jahresperiode',
                }[assignment['reason']] ??
                'Gesondert zu klärende Zuordnung',
          ),
          line(
            'Steuerjahr / Beitragsjahr',
            '${assignment['tax_year']} / ${assignment['social_year']}',
          ),
          line(
            'Ende der zugeordneten Originalperiode',
            businessDate(assignment['assigned_period_end']),
          ),
          for (final branch in payrollAnnualBranches.entries)
            line(
              '${branch.value}: Einmalbeitragsbasis',
              _money(assignment['bases_minor']?[branch.key]),
            ),
        ],
        if (tax.isNotEmpty) ...[
          line(
            'Jahresarbeitslohn vor diesem Einmalbezug',
            _money(detail['annual_pay_before_minor']),
          ),
          line('Getrennte Lohnsteuer des Einmalbezugs', _money(tax['STS'])),
          line('Solidaritätszuschlag des Einmalbezugs', _money(tax['SOLZS'])),
          line(
            'Kirchensteuer des Einmalbezugs',
            _money(detail['church_tax_minor']),
          ),
        ],
        if (social.isNotEmpty) ...[
          line(
            'Arbeitnehmerbeiträge des Einmalbezugs',
            _money(social['employee_total_minor']),
          ),
          line(
            'Arbeitgeberbeiträge des Einmalbezugs',
            _money(social['employer_total_minor']),
          ),
        ],
        if (plan['payroll_calculation_complete'] == true) ...[
          line(
            'Gesamte Arbeitnehmerbeiträge',
            _money(plan['employee_social_total_minor']),
          ),
          line(
            'Gesamte Arbeitnehmersteuer',
            _money(plan['employee_tax_minor']),
          ),
          line('Gesamtnetto', _money(plan['net_minor'])),
          line('Belegte Nettoabzüge', _money(plan['net_deductions_minor'])),
          line('Berechneter Auszahlungsbetrag', _money(plan['payout_minor'])),
          if (plan['employee_additional_payment_minor'] != 0)
            line(
              'Erforderliche Arbeitnehmernachzahlung',
              _money(plan['employee_additional_payment_minor']),
            ),
        ],
        for (final blocker in plan['blockers'] as List? ?? [])
          Notice(
            blocker is Map
                ? '${blocker['message'] ?? blocker['reason'] ?? blocker['code']}'
                : '$blocker',
            error: true,
          ),
        const Notice(
          'Die laufende Rechnung bleibt erhalten. Dieser Fall verbindet sie mit genau einem belegten Einmalanspruch. Tatsächliche Zahlung und amtliche Übermittlung werden gesondert bestätigt.',
        ),
      ],
    );
  }
}

class BusinessPayrollOneoffCasesPage extends StatefulWidget {
  const BusinessPayrollOneoffCasesPage({
    super.key,
    required this.session,
    required this.employee,
    required this.onOriginal,
    required this.onCalculate,
    this.initialMonth,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final Future<void> Function(Map<String, dynamic>) onOriginal, onCalculate;
  final String? initialMonth;
  @override
  State<BusinessPayrollOneoffCasesPage> createState() =>
      _BusinessPayrollOneoffCasesPageState();
}

class _BusinessPayrollOneoffCasesPageState
    extends State<BusinessPayrollOneoffCasesPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get commandKey => 'payroll-oneoff-cases-$employeeId';
  late String month;
  Map<String, dynamic>? sources, selected, preview, previewBody, correction;
  List<Map<String, dynamic>> history = [];
  bool loading = false, busy = false, historical = false, suspended = false;
  String? error;
  Object? generation;
  bool? approvalState;
  int epoch = 0;
  final privateDialogs = <DialogRoute<dynamic>>[];
  final pageScroll = ScrollController();
  bool get readable => !suspended && payrollOneoffCasesReadable(session);
  bool get permitted =>
      readable && !session.readonly && session.can('personnel.approve');
  bool get writable =>
      permitted &&
      session.sectionEnabled('personnel') &&
      sources?['writes_enabled'] == true &&
      sources?['can_approve'] == true;
  Map<String, dynamic>? get pending =>
      session.pendingCommandValues(commandKey, path: '/payroll/one-off-cases');
  @override
  void initState() {
    super.initState();
    month =
        widget.initialMonth ?? DateTime.now().toIso8601String().substring(0, 7);
    WidgetsBinding.instance.addObserver(this);
    session.addListener(changed);
    approvalState = permitted;
    load();
  }

  @override
  void didUpdateWidget(covariant BusinessPayrollOneoffCasesPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.employee['id'] != employeeId ||
        oldWidget.initialMonth != widget.initialMonth) {
      oldWidget.session.removeListener(changed);
      session.addListener(changed);
      epoch++;
      dismissPrivateDialogs();
      clear();
      generation = null;
      month = widget.initialMonth ?? month;
      approvalState = permitted;
      unawaited(load());
    }
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    pageScroll.dispose();
    super.dispose();
  }

  void clear() {
    sources = selected = preview = previewBody = correction = null;
    history = [];
    loading = false;
    busy = false;
    error = null;
  }

  void showBeginning() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && pageScroll.hasClients) pageScroll.jumpTo(0);
    });
  }

  void dismissPrivateDialogs() {
    for (final route in privateDialogs.toList().reversed) {
      if (route.isActive) route.navigator?.removeRoute(route);
    }
    privateDialogs.clear();
  }

  Future<T?> privateDialog<T>(WidgetBuilder builder) async {
    final route = DialogRoute<T>(context: context, builder: builder);
    privateDialogs.add(route);
    try {
      return await Navigator.of(context, rootNavigator: true).push(route);
    } finally {
      privateDialogs.remove(route);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused) {
      epoch++;
      suspended = true;
      dismissPrivateDialogs();
      if (mounted) setState(clear);
    } else if (state == AppLifecycleState.resumed && suspended && mounted) {
      setState(() => suspended = false);
      unawaited(load());
    }
  }

  void changed() {
    final approvalLost = approvalState == true && !permitted;
    approvalState = permitted;
    if (mounted &&
        (!readable ||
            approvalLost ||
            generation != null && generation != session.generation)) {
      epoch++;
      dismissPrivateDialogs();
      setState(() {
        clear();
        generation = session.generation;
      });
    }
  }

  void failed(Object e) {
    if (!mounted) return;
    setState(() {
      error = e is ApiException
          ? e.message
          : e is FormatException
          ? e.message
          : 'Der Einmalbezugsvorgang konnte nicht abgeschlossen werden.';
      if (e is ApiException && [401, 403, 404].contains(e.status)) clear();
    });
    showBeginning();
  }

  Future<Map<String, dynamic>> fresh({
    bool write = false,
    bool replay = false,
    String? forMonth,
  }) async {
    final opening = epoch;
    await session.load();
    if (opening != epoch || suspended)
      _fail('Die private Ansicht wurde verlassen. Quellen erneut öffnen.', 409);
    if (!mounted || !readable || session.error != null || write && !permitted)
      _fail('Aktuelle globale Personal-Lese- und Freigaberechte fehlen.', 403);
    final wanted = forMonth ?? month;
    payrollFactMonth(wanted);
    if (!wanted.startsWith('2026-'))
      _fail('Einmalbezugsmonat im Jahr 2026 wählen.', 400);
    final captured = session.generation,
        value = payrollOneOffCaseSources(
          await session.read(
            '/payroll/one-off-cases/sources?employee_id=$employeeId&month=$wanted',
          ),
          employeeId,
          wanted,
        );
    if (!mounted ||
        !readable ||
        opening != epoch ||
        captured != session.generation ||
        write && (!permitted || value['can_approve'] != true))
      _fail(
        'Die private Ansicht oder Mitarbeiterfreigabe wurde geändert.',
        403,
      );
    if (write &&
        !replay &&
        (!session.sectionEnabled('personnel') ||
            value['writes_enabled'] != true))
      _fail(
        'Neue Einmalbezugsfälle sind im pausierten Personalbereich gesperrt.',
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
      final page = await fresh();
      if (mounted && captured == epoch)
        setState(() {
          sources = page;
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
    final opening = epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await run();
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    } finally {
      if (mounted && opening == epoch) setState(() => busy = false);
    }
  }

  Future<void> inspect(Map<String, dynamic> fact, {bool old = false}) async {
    final opening = epoch;
    final record = payrollOneOffCaseRecord(fact, employeeId),
        page = await fresh(forMonth: record['details']['month']);
    if (mounted && readable && opening == epoch) {
      setState(() {
        sources = page;
        selected = _copy(record);
        month = record['details']['month'];
        historical = old;
        preview = previewBody = correction = null;
        history = [];
        generation = session.generation;
      });
      showBeginning();
    }
  }

  Future<void> repeat() => act(() async {
    final opening = epoch;
    final result = await session.repeatPayrollOneoffCaseCommand(employeeId);
    if (mounted && readable && opening == epoch)
      await inspect(businessMap(result));
  });
  Future<void> save(
    Map<String, dynamic> body, {
    Map<String, dynamic>? previous,
    Map<String, dynamic>? proof,
  }) async {
    final opening = epoch;
    await fresh(write: true, forMonth: body['details']['month']);
    if (pending != null)
      _fail(
        'Zuerst den unbestätigten ursprünglichen Einmalbezugsauftrag klären.',
        409,
      );
    final result = payrollOneOffCaseRecord(
      await session.command(
        commandKey,
        '/payroll/one-off-cases',
        body,
        validateResult: payrollOneOffCaseValidator(
          body,
          previous: previous,
          preview: proof,
        ),
      ),
      employeeId,
    );
    if (mounted && readable && opening == epoch) await inspect(result);
  }

  Future<Map<String, dynamic>?> choose(
    String title,
    List<BusinessField> fields, {
    String saveLabel = 'Einmalbezugsfall unverbindlich prüfen',
  }) async {
    final opening = epoch;
    Map<String, dynamic>? result;
    await privateDialog<bool>(
      (_) => BusinessEditor(
        session: session,
        title: title,
        fields: fields,
        readPermission: 'personnel.read',
        writePermission: 'personnel.approve',
        readAllowed: () => readable && opening == epoch,
        saveLabel: saveLabel,
        onSave: (values) async {
          await fresh(write: true);
          result = _copy(values);
        },
      ),
    );
    return mounted && readable && opening == epoch ? result : null;
  }

  BusinessField source(
    String name,
    String label,
    dynamic values, {
    dynamic initial,
    bool required = true,
  }) => BusinessField(
    name,
    label,
    type: BusinessInput.choice,
    required: required,
    initial: initial is Map ? initial['id'] : initial,
    choices: {
      if (required) '': 'Bitte ausdrücklich auswählen',
      for (final v in businessItems(values))
        '${v['id']}':
            '${v['details']?['claim_reference'] ?? v['details']?['verification_note'] ?? v['details']?['month'] ?? v['kind']} · Fassung ${v['revision']}',
    },
  );

  Future<void> chooseMonth() async {
    if (busy || pending != null) return;
    final opening = epoch;
    var chosen = month;
    final result = await privateDialog<String>(
      (context) => AlertDialog(
        title: const Text('Einmalbezugsmonat wählen'),
        content: TextFormField(
          initialValue: month,
          decoration: const InputDecoration(labelText: 'Monat (JJJJ-MM)'),
          onChanged: (value) => chosen = value,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, chosen.trim()),
            child: const Text('Monat öffnen'),
          ),
        ],
      ),
    );
    if (result == null || !mounted || !readable || opening != epoch) return;
    try {
      payrollFactMonth(result);
      if (!result.startsWith('2026-'))
        _fail('Einmalbezugsmonat im Jahr 2026 wählen.');
      setState(() {
        month = result;
        clear();
      });
      await load();
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> edit([Map<String, dynamic>? previous]) async {
    if (busy || pending != null) return;
    final opening = epoch;
    try {
      final wanted = previous?['details']['month'] ?? month,
          page = await fresh(write: true, forMonth: wanted),
          d = businessMap(previous?['details']);
      if (!mounted || !readable || opening != epoch) return;
      List<Map<String, dynamic>> annual(String kind, {int? year}) =>
          businessItems(page['annual_facts'])
              .where(
                (v) =>
                    v['kind'] == kind &&
                    v['status'] == 'active' &&
                    (year == null || v['details']['year'] == year) &&
                    (kind != 'one_off_earning' ||
                        v['details']['planned_receipt_date'].startsWith(
                          wanted,
                        )) &&
                    (kind != 'annual_tax_forecast' ||
                        v['details']['receipt_date'].startsWith(wanted)),
              )
              .toList();
      final values = await choose(
        previous == null
            ? 'Einmalbezugsfall erfassen'
            : 'Einmalbezugsfall berichtigen',
        [
          source(
            'running_calculation_case_id',
            'Unveränderter laufender Gesamtfall dieses Monats',
            businessItems(page['calculation_cases'])
                .where(
                  (v) =>
                      v['status'] == 'active' &&
                      v['details']['month'] == wanted,
                )
                .toList(),
            initial: d['running_calculation_case_ref'],
          ),
          source(
            'one_off_earning_id',
            'Genau ein belegter Einmalanspruch',
            annual('one_off_earning'),
            initial: d['one_off_earning_ref'],
          ),
          source(
            'current_annual_basis_id',
            'Vollständige Jahresbasis 2026',
            annual('annual_basis', year: 2026),
            initial: d['current_annual_basis_ref'],
          ),
          source(
            'previous_annual_basis_id',
            'Belegte Jahresbasis 2025, falls für die Märzklausel benötigt',
            annual('annual_basis', year: 2025),
            initial: d['previous_annual_basis_ref'],
            required: false,
          ),
          source(
            'annual_tax_forecast_id',
            'Passende Jahressteuergrundlage für diesen Anspruch',
            annual('annual_tax_forecast'),
            initial: d['annual_tax_forecast_ref'],
          ),
          BusinessField(
            'source_file_ids',
            'Geschützte Originale für diesen Einmalbezugsfall',
            type: BusinessInput.multiple,
            required: true,
            initial: previous?['source_file_ids'],
            choices: {
              for (final f in businessItems(page['files']))
                '${f['id']}': '${f['filename']}',
            },
          ),
          BusinessField(
            'verification_note',
            'Nachvollziehbare Beurteilung der konkreten Zuordnung',
            required: true,
            initial: d['verification_note'],
          ),
          if (previous != null)
            const BusinessField(
              'correction_reason',
              'Belegter Korrekturgrund',
              required: true,
            ),
          const BusinessField(
            'confirmed',
            'Ich bestätige die vollständigen Originalquellen und die konkrete Einmalbezugszuordnung.',
            type: BusinessInput.toggle,
          ),
        ],
      );
      if (values == null || !mounted || !readable || opening != epoch) return;
      if (values['confirmed'] != true)
        _fail('Die konkrete Einmalbezugszuordnung ausdrücklich bestätigen.');
      await act(() async {
        await fresh(write: true, forMonth: wanted);
        if (opening != epoch) return;
        final body = payrollOneOffCaseInput(employeeId, page, {
          ...values,
          'month': wanted,
        }, previous: previous);
        final checked = payrollOneOffCasePreview(
          await session.api.call(
            session.path('/payroll/one-off-cases/preview'),
            payrollOneOffCasePreviewInput(body),
          ),
          body,
        );
        if (!mounted || !readable || opening != epoch) return;
        setState(() {
          month = wanted;
          sources = page;
          preview = checked;
          previewBody = {...body, 'preview_hash': checked['preview_hash']};
          correction = previous == null ? null : _copy(previous);
          selected = null;
          history = [];
          generation = session.generation;
        });
        showBeginning();
      });
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> confirm() async {
    if (preview == null || previewBody == null || !writable || pending != null)
      return;
    final opening = epoch,
        proof = _copy(preview!),
        body = _copy(previewBody!),
        prior = correction == null ? null : _copy(correction!);
    final ok = await privateDialog<bool>(
      (context) => AlertDialog(
        title: const Text('Geprüften Einmalbezugsfall festhalten'),
        content: const Text(
          'Ich bestätige genau diese geprüfte Zuordnung, ihre Originale und den ausgewiesenen Berechnungsumfang.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Einmalbezugsfall festhalten'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted || !readable || opening != epoch) return;
    await act(() => save(body, previous: prior, proof: proof));
  }

  Future<void> cancel(Map<String, dynamic> fact) async {
    if (busy || pending != null) return;
    final opening = epoch;
    try {
      await fresh(write: true, forMonth: fact['details']['month']);
      if (!mounted || !readable || opening != epoch) return;
      final reason = await choose('Fälschlichen Einmalbezugsfall aufheben', [
        const BusinessField(
          'correction_reason',
          'Belegter Aufhebungsgrund',
          required: true,
        ),
        const BusinessField(
          'confirmed',
          'Ich bestätige die Aufhebung; frühere Abrechnungen bleiben unverändert.',
          type: BusinessInput.toggle,
        ),
      ], saveLabel: 'Einmalbezugsfall belegt aufheben');
      if (reason == null || !mounted || !readable || opening != epoch) return;
      if (reason['confirmed'] != true)
        _fail('Die Aufhebung ausdrücklich bestätigen.');
      await act(() async {
        final page = await fresh(
          write: true,
          forMonth: fact['details']['month'],
        );
        await save({
          'employee_id': employeeId,
          'employee_revision': page['employee']['revision'],
          'kind': 'one_off_case',
          'rule_version': payrollOneOffRule,
          'source_contract_version': 1,
          'id': fact['id'],
          'revision': fact['revision'],
          'status': 'void',
          'details': _copy(fact['details']),
          'source_file_ids': List<String>.from(fact['source_file_ids']),
          'preview_hash': fact['preview_hash'],
          'correction_reason': reason['correction_reason'],
          'confirmed': true,
        }, previous: fact);
      });
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> showHistory(Map<String, dynamic> fact) => act(() async {
    final opening = epoch;
    await fresh(forMonth: fact['details']['month']);
    final page = businessMap(
          await session.read('/payroll/one-off-cases/${fact['id']}/history'),
        ),
        items = businessItems(page['items']);
    if (items.indexed.any(
      (entry) =>
          payrollOneOffCaseRecord(entry.$2, employeeId)['id'] != fact['id'] ||
          entry.$2['revision'] != entry.$1 + 1,
    ))
      _fail(
        'Die Einmalbezugshistorie gehört nicht zur ursprünglichen Fassung.',
      );
    if (mounted && readable && opening == epoch)
      setState(() => history = items);
  });
  Future<void> calculate(Map<String, dynamic> fact) => act(() async {
    final opening = epoch,
        page = await fresh(write: true, forMonth: fact['details']['month']);
    final current = businessItems(page['one_off_cases'])
        .where(
          (v) =>
              v['id'] == fact['id'] &&
              v['content_hash'] == fact['content_hash'] &&
              v['status'] == 'active',
        )
        .firstOrNull;
    if (current == null ||
        current['plan']['payroll_calculation_complete'] != true)
      _fail(
        'Die aktuelle berechenbare Einmalbezugsfassung erneut öffnen.',
        409,
      );
    if (mounted && readable && opening == epoch)
      await widget.onCalculate(_copy(current));
  });
  Widget recordView(Map<String, dynamic> value) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Einmalbezugsfall ${value['details']['month']} · Fassung ${value['revision']}',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          Text(
            value['status'] == 'void'
                ? 'Aufgehoben'
                : historical
                ? 'Historische Originalfassung'
                : 'Aktiv',
          ),
          Text('${value['details']['verification_note']}'),
          if (value['correction_reason'] != '')
            Text('Belegter Grund: ${value['correction_reason']}'),
          PayrollOneoffCasePlanView(plan: businessMap(value['plan'])),
          for (final file in businessItems(value['sources']['source_files']))
            TextButton(
              onPressed: busy
                  ? null
                  : () => act(() async {
                      await fresh(forMonth: value['details']['month']);
                      await widget.onOriginal(_copy(file));
                    }),
              child: Text('Personaloriginal: ${file['filename']}'),
            ),
          if (!historical)
            OutlinedButton(
              onPressed: busy ? null : () => showHistory(value),
              child: const Text('Einmalbezugsfallhistorie öffnen'),
            ),
          if (!historical &&
              value['status'] == 'active' &&
              writable &&
              pending == null)
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                if (value['plan']['payroll_calculation_complete'] == true)
                  FilledButton(
                    onPressed: busy ? null : () => calculate(value),
                    child: const Text(
                      'Lohn mit diesem Einmalbezugsfall berechnen',
                    ),
                  ),
                OutlinedButton(
                  onPressed: busy ? null : () => edit(value),
                  child: const Text('Einmalbezugsfall berichtigen'),
                ),
                OutlinedButton(
                  onPressed: busy ? null : () => cancel(value),
                  child: const Text('Fälschlichen Einmalbezugsfall aufheben'),
                ),
              ],
            ),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text('Einmalbezüge · ${widget.employee['name']}'),
      actions: [
        IconButton(
          tooltip: 'Rechte und Einmalbezugsquellen aktualisieren',
          onPressed: busy || loading ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !readable
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: BusinessEmpty(
              'Einmalbezugsfälle nicht freigegeben',
              'Diese privaten Nachweise benötigen aktuelle globale Personal-Leserechte.',
            ),
          )
        : ListView(
            controller: pageScroll,
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Ein belegter Einmalanspruch wird mit dem unveränderten laufenden Monatsfall und den tatsächlichen Jahresgrundlagen geprüft.',
              ),
              Text('Gewählter Lohnmonat: $month'),
              OutlinedButton(
                onPressed: busy || pending != null ? null : chooseMonth,
                child: const Text('Einmalbezugsmonat wählen'),
              ),
              if (error != null) Notice(error!, error: true),
              if (loading || busy) const LinearProgressIndicator(),
              if (pending != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Einmalbezugsbestätigung offen'),
                        const Notice(
                          'Der Auftrag kann bereits angenommen sein. Die Wiederholung erhält dieselben Angaben und dieselbe Vorgangskennung.',
                        ),
                        if (permitted)
                          FilledButton(
                            onPressed: busy ? null : repeat,
                            child: const Text(
                              'Ursprünglichen Einmalbezugsauftrag erneut senden',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              if (preview != null) ...[
                Text(
                  'Einmalbezugsfall prüfen',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                PayrollOneoffCasePlanView(plan: businessMap(preview!['plan'])),
                if (preview!['can_confirm'] == true &&
                    writable &&
                    pending == null)
                  FilledButton(
                    onPressed: busy ? null : confirm,
                    child: const Text('Geprüften Einmalbezugsfall festhalten'),
                  ),
              ],
              if (selected != null) recordView(selected!),
              for (final fact in history)
                ListTile(
                  title: Text(
                    'Historische Einmalbezugsfassung ${fact['revision']}',
                  ),
                  subtitle: Text('${fact['correction_reason']}'),
                  onTap: busy
                      ? null
                      : () => act(() => inspect(fact, old: true)),
                ),
              const Text('Gespeicherte Einmalbezugsfälle'),
              for (final fact in businessItems(
                sources?['one_off_cases'] ?? [],
              ).where((v) => v['details']['month'] == month))
                ListTile(
                  title: Text(
                    'Einmalbezugsfall ${fact['details']['month']} · Fassung ${fact['revision']}',
                  ),
                  subtitle: Text(
                    fact['status'] == 'void' ? 'Aufgehoben' : 'Aktiv',
                  ),
                  onTap: busy ? null : () => act(() => inspect(fact)),
                ),
              if (writable && pending == null)
                FilledButton(
                  onPressed: busy ? null : () => edit(),
                  child: const Text('Einmalbezugsfall erfassen'),
                ),
              if (sources?['writes_enabled'] == false)
                const Notice(
                  'Das Personalmodul ist pausiert. Originalfassungen und unveränderte bereits angenommene Aufträge bleiben mit aktuellen Rechten zugänglich.',
                ),
            ],
          ),
  );
}

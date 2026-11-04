import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_payroll_annual_basis_contract.dart';
export 'business_payroll_annual_basis_contract.dart';
import 'business_payroll_annual_basis_forms.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
String _money(dynamic value) => value is int
    ? businessMoney(
        '${value ~/ 100}.${(value.abs() % 100).toString().padLeft(2, '0')}',
      )
    : 'Nicht belegt';
bool payrollAnnualBasisReadable(BusinessSession session) =>
    session.allowed &&
    session.projectId == null &&
    session.hasFeature('payroll_annual_basis') &&
    session.hasModule('payroll_annual_basis') &&
    session.can('personnel.read');

class PayrollAnnualPlanView extends StatelessWidget {
  const PayrollAnnualPlanView({super.key, required this.plan});
  final Map<String, dynamic> plan;
  Widget line(String name, String value) =>
      ListTile(dense: true, title: Text(name), subtitle: Text(value));
  @override
  Widget build(BuildContext context) {
    final kind = plan['kind'];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (kind == 'imported_period') ...[
          line(
            'Tatsächliche Originalperiode',
            '${businessDate(plan['period_start'])} – ${businessDate(plan['period_end'])}',
          ),
          line('Laufendes Originalbrutto', _money(plan['running_gross_minor'])),
          line(
            'Laufender steuerpflichtiger Originalbezug',
            _money(plan['running_taxable_minor']),
          ),
          const Notice(
            'Die externe Abrechnung wird als belegtes Original übernommen. Ihre ursprüngliche Steuer wird nicht neu berechnet.',
          ),
        ],
        if (kind == 'imported_one_off') ...[
          line(
            'Bereits zugeflossener Originalbezug',
            _money(plan['amount_minor']),
          ),
          line(
            'Ursprüngliches Ende der SV-Zuordnungsperiode',
            businessDate(plan['assigned_period_end']),
          ),
          line(
            'SV-Jahr / Steuerjahr',
            '${plan['social_year']} / ${plan['tax_year']}',
          ),
          for (final branch in payrollAnnualBranches.entries)
            line(
              '${branch.value}: bereits verbeitragt',
              _money(plan['bases_minor']?[branch.key]),
            ),
        ],
        if (kind == 'annual_basis') ...[
          line('Beurteilungsstichtag', businessDate(plan['as_of_date'])),
          line('Vollständig gedeckt bis', businessDate(plan['coverage_to'])),
          line(
            'Laufende steuerpflichtige Vorbezüge',
            _money(plan['running_taxable_minor']),
          ),
          line(
            'Frühere steuerpflichtige Einmalbezüge',
            _money(plan['earlier_other_taxable_minor']),
          ),
          if (plan['contains_planned_current_period'] == true)
            const Notice(
              'Die Jahresbasis enthält einen ausdrücklich geplanten laufenden Schlussmonat. Ein tatsächlicher Zufluss bleibt gesondert zu belegen.',
            ),
          for (final section in businessMap(plan['section_rooms']).entries)
            ExpansionTile(
              title: Text(
                section.key == 'minijob'
                    ? 'Beitragsräume im Minijob'
                    : 'Beitragsräume in regulärer Beschäftigung',
              ),
              children: [
                for (final branch in payrollAnnualBranches.entries) ...[
                  line(
                    '${branch.value}: SV-Tage',
                    '${section.value[branch.key]?['sv_days']}',
                  ),
                  line(
                    '${branch.value}: anteilige Grenze',
                    _money(section.value[branch.key]?['partial_cap_minor']),
                  ),
                  line(
                    '${branch.value}: bereits verbeitragt',
                    _money(section.value[branch.key]?['contributed_minor']),
                  ),
                  line(
                    '${branch.value}: verbleibender Raum',
                    _money(section.value[branch.key]?['room_minor']),
                  ),
                ],
              ],
            ),
          ExpansionTile(
            title: const Text('Lückenlose Jahresdeckung'),
            children: [
              for (final coverage in businessItems(plan['coverage'] ?? []))
                line(
                  '${businessDate(coverage['start'])} – ${businessDate(coverage['end'])}',
                  payrollAnnualGapReasons[coverage['source']?['kind']] ??
                      'Gebundene tatsächliche Lohnquelle',
                ),
            ],
          ),
        ],
        if (kind == 'one_off_earning') ...[
          line('Geplanter Bruttoanspruch', _money(plan['amount_minor'])),
          line(
            'Ausdrücklich geplanter Zuflusstag',
            businessDate(plan['planned_receipt_date']),
          ),
          const Notice(
            'Geprüft als sonstiger Bezug und einmaliges Arbeitsentgelt. Diese Anspruchsquelle bestätigt keine tatsächliche Zahlung.',
          ),
        ],
        if (kind == 'annual_tax_forecast') ...[
          line('Beurteilungs-/Zuflusstag', businessDate(plan['receipt_date'])),
          line(
            'Jahresarbeitslohn vor aktuellem Einmalbezug',
            _money(plan['annual_pay_before_minor']),
          ),
          line(
            'Aktueller Einmalbezug, gesondert',
            _money(plan['one_off_minor']),
          ),
          line(
            'Belegte künftige Monatsbezüge',
            _money(plan['forecast_future_minor']),
          ),
          line(
            'Belegte Vorarbeitgeberbezüge',
            _money(plan['previous_employer_minor']),
          ),
          line(
            'Weitere belegte steuerliche Zuflüsse',
            _money(plan['additional_evidenced_tax_receipts_minor']),
          ),
          line('Jahresfreibetrag', _money(plan['annual_allowance_minor'])),
          line(
            'Jahreshinzurechnungsbetrag',
            _money(plan['annual_addition_minor']),
          ),
          const Notice(
            'Der aktuelle Einmalbezug ist in der Jahresbasis noch nicht enthalten. Die Prüfung erzeugt keinen Zahlungsnachweis.',
          ),
        ],
      ],
    );
  }
}

class BusinessPayrollAnnualBasisPage extends StatefulWidget {
  const BusinessPayrollAnnualBasisPage({
    super.key,
    required this.session,
    required this.employee,
    required this.onOriginal,
    this.onSelected,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final Future<void> Function(Map<String, dynamic>) onOriginal;
  final Future<void> Function(Map<String, dynamic>)? onSelected;
  @override
  State<BusinessPayrollAnnualBasisPage> createState() =>
      _BusinessPayrollAnnualBasisPageState();
}

class _BusinessPayrollAnnualBasisPageState
    extends State<BusinessPayrollAnnualBasisPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get commandKey => 'payroll-annual-basis-$employeeId';
  Map<String, dynamic>? sources, selected, preview, previewBody, correction;
  List<Map<String, dynamic>> history = [];
  bool loading = false, busy = false, historical = false, suspended = false;
  String? error;
  Object? generation;
  bool? approvalState;
  int epoch = 0;
  final privateDialogs = <DialogRoute<dynamic>>[];
  final pageScroll = ScrollController();
  bool get readable => !suspended && payrollAnnualBasisReadable(session);
  bool get permitted =>
      readable && !session.readonly && session.can('personnel.approve');
  bool get writable =>
      permitted &&
      session.sectionEnabled('personnel') &&
      sources?['writes_enabled'] == true &&
      sources?['can_approve'] == true;
  Map<String, dynamic>? get pending =>
      session.pendingCommandValues(commandKey, path: '/payroll/annual-facts');
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    session.addListener(changed);
    approvalState = permitted;
    load();
  }

  @override
  void didUpdateWidget(covariant BusinessPayrollAnnualBasisPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.employee['id'] != employeeId) {
      oldWidget.session.removeListener(changed);
      session.addListener(changed);
      epoch++;
      dismissPrivateDialogs();
      clear();
      generation = null;
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
          : 'Der Jahresquellenvorgang konnte nicht abgeschlossen werden.';
      if (e is ApiException && [401, 403, 404].contains(e.status)) clear();
    });
    showBeginning();
  }

  Future<Map<String, dynamic>> fresh({
    bool write = false,
    bool replay = false,
  }) async {
    final opening = epoch;
    await session.load();
    if (opening != epoch || suspended)
      _fail('Die private Ansicht wurde verlassen. Quellen erneut öffnen.', 409);
    if (!mounted || !readable || session.error != null || write && !permitted)
      _fail('Aktuelle globale Personal-Lese- und Freigaberechte fehlen.', 403);
    final captured = session.generation,
        value = payrollAnnualSources(
          await session.read(
            '/payroll/annual-facts/sources?employee_id=$employeeId',
          ),
          employeeId,
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
        'Neue Jahresnachweise sind im pausierten Personalbereich gesperrt.',
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
    final record = payrollAnnualRecord(fact, employeeId), page = await fresh();
    if (mounted && readable && opening == epoch) {
      setState(() {
        sources = page;
        selected = _copy(record);
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
    final result = await session.repeatPayrollAnnualBasisCommand(employeeId);
    if (mounted && readable && opening == epoch)
      await inspect(businessMap(result));
  });
  Future<void> save(
    Map<String, dynamic> body, {
    Map<String, dynamic>? previous,
    Map<String, dynamic>? proof,
  }) async {
    final opening = epoch;
    await fresh(write: true);
    if (pending != null)
      _fail(
        'Zuerst den unbestätigten ursprünglichen Jahresquellenauftrag klären.',
        409,
      );
    final result = payrollAnnualRecord(
      await session.command(
        commandKey,
        '/payroll/annual-facts',
        body,
        validateResult: payrollAnnualValidator(
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
    List<BusinessField> fields,
  ) async {
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
        saveLabel: 'Belegte Angaben übernehmen',
        onSave: (values) async {
          await fresh(write: true);
          result = _copy(values);
        },
      ),
    );
    return mounted && readable && opening == epoch ? result : null;
  }

  Future<void> edit(String kind, [Map<String, dynamic>? previous]) async {
    if (busy || pending != null) return;
    final opening = epoch;
    try {
      final page = await fresh(write: true),
          d = businessMap(previous?['details']);
      if (!mounted || !readable || opening != epoch) return;
      final forms = PayrollAnnualForms(page, [], choose);
      final values = await choose(
        '${previous == null ? 'Erfassen' : 'Korrigieren'}: ${payrollAnnualKinds[kind]}',
        [
          forms.source(
            'employer_identity_ref',
            'Belegter Arbeitgeber-/Identitätsstand',
            'identities',
            kinds: ['identity'],
            initial: d['employer_identity_ref'],
          ),
          BusinessField(
            'source_file_ids',
            'Geschützte Originale für diese Jahresquelle',
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
            'Nachvollziehbarer Prüfvermerk zu den Jahresquellen',
            required: true,
            initial: d['verification_note'],
          ),
          if (previous != null)
            const BusinessField(
              'correction_reason',
              'Belegter Korrekturgrund',
              required: true,
            ),
        ],
      );
      if (values == null || !mounted || !readable || opening != epoch) return;
      final details = await PayrollAnnualForms(
        page,
        List<String>.from(values['source_file_ids']),
        choose,
      ).collect(kind, d);
      if (details == null || !mounted || !readable || opening != epoch) return;
      final confirmation = await choose('Konkrete Jahresquellen prüfen', [
        const BusinessField(
          'confirmed',
          'Ich bestätige die konkreten Angaben und die vollständigen zugehörigen Originale.',
          type: BusinessInput.toggle,
        ),
      ]);
      if (confirmation == null || !mounted || !readable || opening != epoch)
        return;
      if (confirmation['confirmed'] != true)
        _fail('Die konkreten Jahresangaben ausdrücklich bestätigen.', 400);
      await act(() async {
        await fresh(write: true);
        if (opening != epoch) return;
        final body = payrollAnnualInput(employeeId, page, kind, {
          ...values,
          'details': {
            ...details,
            'employer_identity_ref': values['employer_identity_ref'],
          },
        }, previous: previous);
        final checked = payrollAnnualPreview(
          await session.api.call(
            session.path('/payroll/annual-facts/preview'),
            payrollAnnualPreviewInput(body),
          ),
          body,
        );
        if (!mounted || !readable || opening != epoch) return;
        setState(() {
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
    final confirmed = await privateDialog<bool>(
      (context) => AlertDialog(
        title: const Text('Geprüfte Jahresquelle festhalten'),
        content: const Text(
          'Ich bestätige genau diese geprüften Jahresangaben und die gebundenen Originale.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Jahresquelle festhalten'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted || !readable || opening != epoch) return;
    await act(() => save(body, previous: prior, proof: proof));
  }

  Future<void> cancel(Map<String, dynamic> fact) async {
    if (busy || pending != null) return;
    final opening = epoch;
    try {
      await fresh(write: true);
      if (!mounted || !readable || opening != epoch) return;
      final reason = await choose('Fälschliche Jahresquelle aufheben', [
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
      ]);
      if (reason == null || !mounted || !readable || opening != epoch) return;
      if (reason['confirmed'] != true)
        _fail('Die Aufhebung ausdrücklich bestätigen.', 400);
      await act(() async {
        final page = await fresh(write: true);
        await save({
          'employee_id': employeeId,
          'employee_revision': page['employee']['revision'],
          'kind': fact['kind'],
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
    await fresh();
    final page = businessMap(
          await session.read('/payroll/annual-facts/${fact['id']}/history'),
        ),
        items = businessItems(page['items']);
    if (page['employee_id'] != employeeId ||
        items.indexed.any(
          (entry) =>
              payrollAnnualRecord(
                    entry.$2,
                    employeeId,
                    kind: fact['kind'],
                  )['id'] !=
                  fact['id'] ||
              entry.$2['revision'] != entry.$1 + 1,
        ))
      _fail(
        'Die Jahresquellenhistorie gehört nicht zur gewählten Originalfassung.',
      );
    if (mounted && readable && opening == epoch)
      setState(() => history = items);
  });

  Future<void> select(Map<String, dynamic> fact) => act(() async {
    final opening = epoch, page = await fresh();
    final current = businessItems(page['annual_facts'])
        .where(
          (v) =>
              v['id'] == fact['id'] &&
              v['content_hash'] == fact['content_hash'] &&
              v['status'] == 'active',
        )
        .firstOrNull;
    if (current == null)
      _fail(
        'Die gewählte aktive Jahresquelle wurde geändert. Ihre aktuelle Fassung erneut öffnen.',
        409,
      );
    if (mounted && readable && opening == epoch && widget.onSelected != null)
      await widget.onSelected!(_copy(current));
  });

  Widget recordView(Map<String, dynamic> value) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${payrollAnnualKinds[value['kind']]} · Fassung ${value['revision']}',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          Text(
            value['status'] == 'void'
                ? 'Aufgehoben'
                : historical
                ? 'Historische Originalfassung'
                : 'Aktiv',
          ),
          Text(
            '${businessDate(value['effective_from'])} – ${businessDate(value['effective_to'])}',
          ),
          Text('${value['details']['verification_note']}'),
          if (value['correction_reason'] != '')
            Text('Belegter Grund: ${value['correction_reason']}'),
          PayrollAnnualPlanView(plan: businessMap(value['plan'])),
          for (final file in businessItems(value['sources']['source_files']))
            TextButton(
              onPressed: busy
                  ? null
                  : () => act(() async {
                      await fresh();
                      await widget.onOriginal(_copy(file));
                    }),
              child: Text('Personaloriginal: ${file['filename']}'),
            ),
          if (!historical)
            OutlinedButton(
              onPressed: busy ? null : () => showHistory(value),
              child: const Text('Jahresquellenhistorie öffnen'),
            ),
          if (!historical && value['status'] == 'active') ...[
            if (widget.onSelected != null)
              FilledButton(
                onPressed: busy || pending != null ? null : () => select(value),
                child: const Text('Diese Jahresquelle auswählen'),
              ),
            if (writable && pending == null)
              Wrap(
                spacing: 12,
                runSpacing: 8,
                children: [
                  OutlinedButton(
                    onPressed: busy ? null : () => edit(value['kind'], value),
                    child: const Text('Jahresquelle korrigieren'),
                  ),
                  OutlinedButton(
                    onPressed: busy ? null : () => cancel(value),
                    child: const Text('Fälschliche Jahresquelle aufheben'),
                  ),
                ],
              ),
          ],
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(
        'Jahresquellen und Einmalbezüge · ${widget.employee['name']}',
      ),
      actions: [
        IconButton(
          tooltip: 'Rechte und Jahresquellen aktualisieren',
          onPressed: busy || loading ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !readable
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: BusinessEmpty(
              'Jahresquellen nicht freigegeben',
              'Diese privaten Nachweise benötigen aktuelle globale Personal-Leserechte.',
            ),
          )
        : ListView(
            controller: pageScroll,
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Originale externer Lohnperioden, tatsächliche Vorbezüge und vollständige Jahresgrundlagen werden als eigene private Quellen geprüft.',
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
                        const Text('Jahresquellenbestätigung offen'),
                        const Notice(
                          'Der Auftrag kann bereits gespeichert sein. Die Wiederholung verwendet dieselben Angaben und dieselbe Vorgangskennung.',
                        ),
                        if (permitted)
                          FilledButton(
                            onPressed: busy ? null : repeat,
                            child: const Text(
                              'Ursprünglichen Jahresquellenauftrag erneut senden',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              if (preview != null) ...[
                Text(
                  'Jahresquelle prüfen',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                PayrollAnnualPlanView(plan: businessMap(preview!['plan'])),
                if (preview!['can_confirm'] == true &&
                    writable &&
                    pending == null)
                  FilledButton(
                    onPressed: busy ? null : confirm,
                    child: const Text('Geprüfte Jahresquelle festhalten'),
                  ),
              ],
              if (selected != null) recordView(selected!),
              for (final fact in history)
                ListTile(
                  title: Text(
                    'Historische Jahresquellenfassung ${fact['revision']}',
                  ),
                  subtitle: Text('${fact['correction_reason']}'),
                  onTap: busy
                      ? null
                      : () => act(() => inspect(fact, old: true)),
                ),
              for (final kind in payrollAnnualKinds.entries)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          kind.value,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        for (final fact in businessItems(
                          sources?['annual_facts'] ?? [],
                        ).where((v) => v['kind'] == kind.key))
                          ListTile(
                            title: Text(
                              '${businessDate(fact['effective_from'])} – ${businessDate(fact['effective_to'])} · Fassung ${fact['revision']}',
                            ),
                            subtitle: Text(
                              fact['status'] == 'void' ? 'Aufgehoben' : 'Aktiv',
                            ),
                            onTap: busy ? null : () => act(() => inspect(fact)),
                          ),
                        if (writable && pending == null)
                          FilledButton(
                            onPressed: busy ? null : () => edit(kind.key),
                            child: Text('${kind.value} erfassen'),
                          ),
                      ],
                    ),
                  ),
                ),
              if (sources?['writes_enabled'] == false)
                const Notice(
                  'Das Personalmodul ist pausiert. Frühere Originale und unveränderte bereits angenommene Aufträge bleiben mit aktuellen Rechten zugänglich.',
                ),
            ],
          ),
  );
}

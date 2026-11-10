import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_payroll_calculation_case_contract.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_travel_tax_policies.dart';
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
bool payrollCalculationCasesReadable(BusinessSession session) =>
    session.allowed &&
    session.projectId == null &&
    session.hasFeature('payroll_calculation_cases') &&
    session.hasModule('payroll_calculation_cases') &&
    session.can('personnel.read');

class PayrollCalculationCasePlanView extends StatelessWidget {
  const PayrollCalculationCasePlanView({
    super.key,
    required this.plan,
    this.sources,
  });
  final Map<String, dynamic> plan;
  final Map<String, dynamic>? sources;
  Widget line(String title, String value) =>
      ListTile(dense: true, title: Text(title), subtitle: Text(value));
  @override
  Widget build(BuildContext context) {
    if (plan['rule_version'] == payrollFactorTransitionRule ||
        plan['rule_version'] == payrollFactorTransitionPeriodRule) {
      final partial = plan['rule_version'] == payrollFactorTransitionPeriodRule;
      final review = businessMap(
        plan[partial
            ? 'factor_transition_period_assessment'
            : 'factor_transition_assessment'],
      );
      final forecast = businessMap(review['transition_assessment']);
      final component = businessMap(
        plan[partial
            ? 'factor_transition_period_component'
            : 'factor_transition_component'],
      );
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          line(
            partial
                ? 'Midijob-Teilmonat mit belegtem ELStAM-Faktor'
                : 'Midijob mit belegtem ELStAM-Faktor',
            '${plan['month']}',
          ),
          if (partial) ...[
            for (final period in businessItems(plan['employment_intervals']))
              line(
                'Tatsächliche Beschäftigung',
                '${businessDate(period['start'])} – ${businessDate(period['end'])}',
              ),
            for (final period in businessItems(plan['tax_periods']))
              line('Steuertage', '${period['tax_days']}'),
            for (final period in businessItems(plan['social_periods']))
              line('SV-Tage', '${period['days']}'),
            line('Tatsächliches Teilbrutto', _money(plan['gross_minor'])),
          ],
          line(
            'Eingetragener ELStAM-Faktor',
            '${plan['factor_parameters']['tax_factor']}'.replaceAll('.', ','),
          ),
          line(
            'Belegter regelmäßiger Monatslohn',
            _money(forecast['regular_monthly_gross_minor']),
          ),
          line('Prognosezeitraum', '${forecast['forecast_months']} Monate'),
          line(
            'Gesamt-Beitragsbasis',
            _money(component['transition']?['total_assessment_minor']),
          ),
          line(
            'Arbeitnehmer-Beitragsbasis',
            _money(component['transition']?['employee_assessment_minor']),
          ),
          line('Lohnsteuer', _money(component['individual_wage_tax_minor'])),
          line('Netto', _money(component['net_minor'])),
          line('Personenbezogene Prüfung', '${review['verification_note']}'),
          for (final blocker in businessItems(plan['blockers']))
            Notice('${blocker['message']}', error: true),
          Notice(
            plan['can_calculate'] == true
                ? partial
                      ? 'Der belegte Eintritts-/Austrittsteilmonat ist im angezeigten Umfang berechenbar. Lohnabschluss und tatsächliche Zahlung bleiben gesondert.'
                      : 'Der vollständig belegte Faktor-Midijob ist im angezeigten Umfang berechenbar. Lohnabschluss und tatsächliche Zahlungen erfolgen gesondert.'
                : 'Die offenen fachlichen Punkte sperren den Lohnabschluss.',
          ),
        ],
      );
    }
    if (plan['rule_version'] == individualMinijobRule) {
      final assessment = businessMap(plan['individual_minijob_assessment']);
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          line(
            'Individuell besteuerter Minijob',
            '${plan['month']} · ${_money(plan['gross_minor'])}',
          ),
          line(
            'Tatsächliche Krankenversicherung',
            const {
                  'statutory_family':
                      'Beitragsfreie gesetzliche Familienversicherung',
                  'statutory_mandatory': 'Gesetzlich pflichtversichert',
                  'statutory_voluntary': 'Gesetzlich freiwillig versichert',
                  'private': 'Privat versichert',
                  'unknown': 'Noch nicht belegt',
                }[plan['actual_health_insurance']] ??
                'Noch nicht belegt',
          ),
          if (assessment['pension_status'] != null)
            line(
              'Belegter Rentenversicherungsstatus',
              const {
                    'exempt': 'Wirksam befreit',
                    'compulsory': 'Rentenversicherungspflichtig',
                    'unknown': 'Noch nicht belegt',
                  }[assessment['pension_status']] ??
                  'Noch nicht belegt',
            ),
          if (assessment['declaration_date'] != null)
            line(
              'Persönliche Prüfung vom',
              businessDate(assessment['declaration_date']),
            ),
          for (final row in businessItems(plan['employment_intervals']))
            line(
              'Belegter Beschäftigungszeitraum',
              '${businessDate(row['start'])} – ${businessDate(row['end'])}',
            ),
          for (final blocker in businessItems(plan['blockers']))
            Notice('${blocker['message']}', error: true),
          Notice(
            plan['can_calculate'] == false
                ? 'Die Originalprüfung bleibt erhalten. Dieser Fall ist gesperrt und weist keinen berechneten Nettobetrag aus.'
                : 'Die Originale belegen diese Person und diesen Monat. Die Berechnung erzeugt keine tatsächliche Auszahlung.',
          ),
        ],
      );
    }
    String interval(Map<String, dynamic> p) =>
        '${businessDate(p['start'])} – ${businessDate(p['end'])}';
    String earningDates(Map<String, dynamic> p) {
      if (p['start'] is String && p['end'] is String) return interval(p);
      final dates = p['claim_dates'] ?? p['days'];
      return dates is List && dates.isNotEmpty
          ? dates.map(businessDate).join(', ')
          : 'Kein belegter Anspruchstag';
    }

    final travel = businessMap(plan['travel']),
        tax = businessMap(plan['flat_travel_tax']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        line('Abrechnungsmonat', '${plan['month']}'),
        if (plan['factor_parameters'] != null)
          line(
            'Eingetragener Faktor',
            '${plan['factor_parameters']['tax_factor']}'.replaceAll('.', ','),
          ),
        line(
          'Brutto einschließlich Lohn-Reisebeträgen',
          _money(plan['gross_minor']),
        ),
        for (final p in businessItems(plan['employment_intervals']))
          line(
            'Beschäftigung',
            '${interval(p)} · ${p['calendar_days']} Kalendertage',
          ),
        for (final p in businessItems(plan['earnings']))
          line(
            const {
                  'ordinary_work': 'Regelmäßiges Arbeitsentgelt',
                  'sickness': 'Entgeltfortzahlung bei Krankheit',
                  'public_holiday': 'Feiertagsvergütung',
                  'vacation': 'Urlaubsentgelt',
                }[p['kind']] ??
                'Belegter Entgeltanspruch',
            '${earningDates(p)} · ${_money(p['gross_minor'])}',
          ),
        for (final p in businessItems(plan['tax_periods']))
          line(
            'Lohnsteuerzeitraum',
            '${interval(p)} · ${p['tax_days']} Steuertage',
          ),
        for (final p in businessItems(plan['social_periods']))
          line(
            'Sozialversicherung',
            '${interval(p)} · ${p['days']} SV-Tage · ${_money(p['gross_minor'])}',
          ),
        if ((plan['unpaid_dates'] as List?)?.isNotEmpty == true)
          line(
            'Tage ohne Entgeltanspruch',
            (plan['unpaid_dates'] as List).map(businessDate).join(', '),
          ),
        line(
          'Steuerfreie Reiseerstattung über Reisekostenzahlung',
          _money(travel['tax_free_external_minor']),
        ),
        if (plan['travel_paid_minor'] != null) ...[
          line(
            'Bereits außerhalb des Lohns erstattet',
            _money(plan['travel_paid_minor']),
          ),
          const Notice(
            'Die nachgewiesene steuerfreie Reiseerstattung wird nicht nochmals zum Lohnnetto addiert.',
          ),
          if (sources != null)
            for (final source in businessItems(sources!['travel_sources']))
              for (final payment in businessItems(
                source['payment_proof']['payments'],
              ))
                line(
                  payment['kind'] == 'repayment'
                      ? 'Belegte Reiserückzahlung'
                      : 'Belegte Reiseerstattung',
                  '${businessDate(payment['paid_on'])} · ${_money(payment['amount_minor'])}${payment['status'] == 'void' ? ' · Historisch aufgehoben' : ''}',
                ),
        ],
        line(
          'Pauschal versteuerte Erstattung im Lohn',
          _money(travel['flat_taxable_payroll_minor']),
        ),
        line(
          'Individuell versteuerte Erstattung im Lohn',
          _money(travel['individual_taxable_payroll_minor']),
        ),
        line(
          'Reisesachbezug ohne zusätzliche Barauszahlung',
          _money(travel['benefit_in_kind_non_cash_minor']),
        ),
        line(
          'Mahlzeitenmerkmal M',
          travel['letter_m'] == true ? 'Belegt' : 'Nicht ausgelöst',
        ),
        if (tax.isNotEmpty) ...[
          line(
            'Pauschalsteuer einschließlich Nebensteuern',
            _money(tax['statutory_employer_due_minor']),
          ),
          line(
            'Belegter Arbeitnehmerabzug für Steuerkosten',
            _money(tax['employee_tax_minor']),
          ),
          line(
            'Sozialversicherung des pauschalierten Betrags',
            tax['social_exempt'] == true
                ? 'Nach den belegten Fristen beitragsfrei'
                : 'Beitragspflichtig',
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
          'Dieser Fall hält die geprüften Ansprüche und Quellen fest. Die anschließende Lohnabrechnung berechnet Netto und Beiträge. Tatsächliche Zahlung und Übermittlung bleiben gesonderte Vorgänge.',
        ),
      ],
    );
  }
}

class BusinessPayrollCalculationCasesPage extends StatefulWidget {
  const BusinessPayrollCalculationCasesPage({
    super.key,
    required this.session,
    required this.employee,
    required this.onOriginal,
    required this.onCalculate,
    this.initialMonth,
    this.onPolicyOriginal,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final Future<void> Function(Map<String, dynamic>) onOriginal, onCalculate;
  final PayrollTravelPolicyOriginal? onPolicyOriginal;
  final String? initialMonth;
  @override
  State<BusinessPayrollCalculationCasesPage> createState() =>
      _BusinessPayrollCalculationCasesPageState();
}

class _BusinessPayrollCalculationCasesPageState
    extends State<BusinessPayrollCalculationCasesPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get commandKey => 'payroll-calculation-cases-$employeeId';
  late String month;
  Map<String, dynamic>? sources, selected, preview, previewBody, correction;
  List<Map<String, dynamic>> history = [];
  bool busy = false, loading = false, historical = false, suspended = false;
  final privateDialogs = <Route<dynamic>>{};
  String? error;
  Object? generation, activeAction;
  bool? approvalState;
  int epoch = 0;
  final pageScroll = ScrollController();
  void showBeginning() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && pageScroll.hasClients) pageScroll.jumpTo(0);
    });
  }

  bool get readable => !suspended && payrollCalculationCasesReadable(session);
  bool get permitted =>
      readable && !session.readonly && session.can('personnel.approve');
  bool get writable =>
      permitted &&
      session.sectionEnabled('personnel') &&
      sources?['writes_enabled'] == true &&
      sources?['can_approve'] == true;
  Map<String, dynamic>? get pending => session.pendingCommandValues(
    commandKey,
    path: '/payroll/calculation-cases',
  );
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
  void didUpdateWidget(
    covariant BusinessPayrollCalculationCasesPage oldWidget,
  ) {
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
    pageScroll.dispose();
    session.removeListener(changed);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void clear() {
    sources = selected = preview = previewBody = correction = null;
    history = [];
    loading = false;
    busy = false;
    activeAction = null;
    error = null;
  }

  void dismissPrivateDialogs() {
    for (final route in privateDialogs.toList()) {
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

  void failed(Object e) {
    if (!mounted) return;
    setState(() {
      error = e is ApiException
          ? e.message
          : e is FormatException
          ? e.message
          : 'Der Abrechnungsfall konnte nicht abgeschlossen werden.';
      if (e is ApiException && [401, 403, 404].contains(e.status)) clear();
    });
    showBeginning();
  }

  Future<Map<String, dynamic>> fresh({
    bool write = false,
    String? forMonth,
  }) async {
    final opening = epoch;
    await session.load();
    if (opening != epoch || suspended)
      _fail('Die private Ansicht wurde verlassen. Quellen erneut öffnen.', 409);
    if (!mounted || !readable || session.error != null || write && !permitted)
      _fail('Aktuelle globale Personal-Lese- und Freigaberechte fehlen.', 403);
    final captured = session.generation, wanted = forMonth ?? month;
    payrollFactMonth(wanted);
    final result = payrollCalculationCaseSources(
      await session.read(
        '/payroll/calculation-cases/sources?employee_id=$employeeId&month=$wanted',
      ),
      employeeId,
      wanted,
    );
    if (!mounted ||
        !readable ||
        opening != epoch ||
        captured != session.generation ||
        write && (!permitted || result['can_approve'] != true))
      _fail(
        'Die private Ansicht oder Mitarbeiterfreigabe wurde geändert.',
        403,
      );
    if (write &&
        (!session.sectionEnabled('personnel') ||
            result['writes_enabled'] != true))
      _fail(
        'Neue Abrechnungsfälle sind im pausierten Personalbereich gesperrt.',
        423,
      );
    return result;
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
    final opening = epoch, action = Object();
    setState(() {
      activeAction = action;
      busy = true;
      error = null;
    });
    try {
      await run();
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    } finally {
      if (mounted && identical(activeAction, action)) {
        setState(() {
          activeAction = null;
          busy = false;
        });
      }
    }
  }

  Future<void> inspect(Map<String, dynamic> fact, {bool old = false}) async {
    final opening = epoch;
    final record = payrollCalculationCaseRecord(fact, employeeId),
        page = await fresh(forMonth: fact['details']['month']);
    if (mounted && readable && opening == epoch) {
      setState(() {
        month = record['details']['month'];
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
    final result = await session.repeatPayrollCalculationCaseCommand(
      employeeId,
    );
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
    if (body['rule_version'] == payrollFactorTransitionPeriodRule &&
        !session.hasFeature(payrollFactorTransitionPeriodFeature))
      _fail(
        'Die aktuelle Freigabe für den Faktor-/Midijob-Teilmonat fehlt.',
        403,
      );
    if (body['rule_version'] == payrollFactorTransitionRule &&
        !session.hasFeature(payrollFactorTransitionFeature))
      _fail('Die aktuelle Freigabe für den Faktor-Midijob fehlt.', 403);
    if (body['rule_version'] == individualMinijobRule &&
        !session.hasFeature(individualMinijobFeature))
      _fail('Die Freigabe für den individuellen Minijob fehlt.', 403);
    if (body['rule_version'] == payrollFactorClaimTravelRule &&
        !session.hasFeature(payrollFactorClaimTravelFeature))
      _fail(
        'Die aktuelle Freigabe für Faktor, Ansprüche und bezahlte Reisen fehlt.',
        403,
      );
    if (body['rule_version'] == payrollFactorClaimsRule &&
        !session.hasFeature(payrollFactorClaimsFeature))
      _fail('Die aktuelle Freigabe für den Faktor-Anspruchsfall fehlt.', 403);
    if (body['rule_version'] == payrollFactorTaxfreeTravelRule &&
        !session.hasFeature('payroll_factor_taxfree_travel'))
      _fail('Die aktuelle Freigabe für den Faktor-Reisefall fehlt.', 403);
    if (pending != null)
      _fail(
        'Zuerst den ursprünglichen offenen Abrechnungsauftrag klären.',
        409,
      );
    final result = payrollCalculationCaseRecord(
      await session.command(
        commandKey,
        '/payroll/calculation-cases',
        body,
        validateResult: payrollCalculationCaseValidator(
          body,
          previous: previous,
          preview: proof,
        ),
      ),
      employeeId,
    );
    if (mounted && readable && opening == epoch) await inspect(result);
  }

  Map<String, String> choices(
    dynamic values,
    String Function(Map<String, dynamic>) label, {
    bool empty = true,
  }) => {
    if (empty) '': 'Bitte ausdrücklich auswählen',
    for (final v in businessItems(values)) '${v['id']}': label(v),
  };
  List<String> ids(dynamic values) =>
      businessItems(values ?? []).map((v) => '${v['id']}').toList();
  BusinessField files(
    Map<String, dynamic> page,
    String name,
    String label, {
    dynamic initial,
    bool multiple = true,
    bool required = true,
  }) => BusinessField(
    name,
    label,
    type: multiple ? BusinessInput.multiple : BusinessInput.choice,
    required: required,
    initial: initial,
    choices: choices(
      page['files'],
      (v) => '${v['filename']}',
      empty: !multiple && required,
    ),
  );
  Future<Map<String, dynamic>?> choose(
    String title,
    List<BusinessField> fields, {
    String saveLabel = 'Angaben übernehmen',
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

  Future<void> chooseMonth() async {
    if (busy || pending != null) return;
    var chosenMonth = month;
    final opening = epoch;
    final chosen = await privateDialog<String>(
      (context) => AlertDialog(
        title: const Text('Abrechnungsmonat wählen'),
        content: TextFormField(
          initialValue: month,
          onChanged: (value) => chosenMonth = value,
          decoration: const InputDecoration(labelText: 'Monat (JJJJ-MM)'),
          keyboardType: TextInputType.datetime,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, chosenMonth.trim()),
            child: const Text('Monat öffnen'),
          ),
        ],
      ),
    );
    if (chosen == null || !mounted || !readable || opening != epoch) return;
    try {
      payrollFactMonth(chosen);
      setState(() {
        month = chosen;
        clear();
      });
      await load();
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> policies() => act(() async {
    await fresh();
    if (!mounted) return;
    await showPayrollTravelTaxPolicies(
      context,
      session: session,
      onOriginal: widget.onPolicyOriginal,
      selectable: false,
    );
    if (mounted && readable) await load();
  });
  Future<void> edit([Map<String, dynamic>? previous]) async {
    if (previous?['rule_version'] == payrollFactorTransitionPeriodRule) {
      await editFactorTransition(previous, true);
      return;
    }
    if (previous?['rule_version'] == payrollFactorTransitionRule) {
      await editFactorTransition(previous);
      return;
    }
    if (previous?['rule_version'] == individualMinijobRule) {
      await editIndividualMinijob(previous);
      return;
    }
    if (previous?['rule_version'] == payrollFactorClaimTravelRule) {
      await editFactorClaims(previous, true);
      return;
    }
    if (previous?['rule_version'] == payrollFactorClaimsRule) {
      await editFactorClaims(previous);
      return;
    }
    if (previous?['rule_version'] == payrollFactorTaxfreeTravelRule) {
      await editFactorTravel(previous);
      return;
    }
    if (busy || pending != null) return;
    final opening = epoch;
    try {
      final page = await fresh(write: true),
          d = businessMap(previous?['details']),
          decision = businessMap(d['flat_tax_decision']);
      if (!mounted || !readable || opening != epoch) return;
      final facts = businessItems(page['facts']),
          oldEvents = businessItems(d['segment_events'] ?? []);
      final values = await choose(
        previous == null
            ? 'Belegten Abrechnungsfall zusammenstellen'
            : 'Abrechnungsfall berichtigen',
        [
          BusinessField(
            'period_case_id',
            'Bestätigter Basisfall dieses Monats',
            type: BusinessInput.choice,
            required: true,
            initial: d['period_case_ref']?['id'],
            choices: choices(
              facts
                  .where(
                    (v) =>
                        v['kind'] == 'period_case' &&
                        v['status'] == 'active' &&
                        v['details']['month'] == month,
                  )
                  .toList(),
              (v) => '${v['details']['month']} · Fassung ${v['revision']}',
            ),
          ),
          BusinessField(
            'employment_terms_ids',
            'Sämtliche Beschäftigungsepisoden',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['employment_terms_refs']),
            choices: choices(
              facts
                  .where(
                    (v) =>
                        v['kind'] == 'employment_terms' &&
                        v['status'] == 'active',
                  )
                  .toList(),
              (v) =>
                  '${businessDate(v['effective_from'])} – ${businessDate(v['effective_to'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'profile_ids',
            'Sämtliche einschlägigen Steuer-/SV-Profile',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['profile_refs']),
            choices: choices(
              page['profiles'],
              (v) =>
                  '${businessDate(v['profile']?['effective_from'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'identity_ids',
            'Sämtliche zugehörigen Identitäts-/Steuernachweise',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['identity_refs']),
            choices: choices(
              page['identities'],
              (v) =>
                  '${businessDate(v['details']?['valid_from'])} – ${businessDate(v['details']?['valid_to'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'entitlement_case_ids',
            'Alle aktiven Ansprüche und Unterbrechungen dieses Monats',
            type: BusinessInput.multiple,
            initial: ids(d['entitlement_case_refs']),
            choices: choices(
              businessItems(page['entitlements'])
                  .where((v) => v['status'] == 'active')
                  .toList(),
              (v) =>
                  '${businessDate(v['effective_from'])} – ${businessDate(v['effective_to'])} · ${v['details']?['verification_note']}',
              empty: false,
            ),
          ),
          BusinessField(
            'travel_settlement_ids',
            'Belegte Reiseabrechnungen für diesen Lohnmonat',
            type: BusinessInput.multiple,
            initial: ids(d['travel_settlement_refs']),
            choices: choices(
              businessItems(page['travel_settlements'])
                  .where((v) => v['status'] == 'approved')
                  .toList(),
              (v) =>
                  'Reise ${v['details']?['from'] ?? v['effective_from'] ?? ''} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'event_count',
            'Anzahl belegter Profilwechsel, auch bekannte 0',
            type: BusinessInput.integer,
            required: true,
            initial: previous == null ? null : oldEvents.length,
          ),
          BusinessField(
            'thirty_day_rule',
            'Zusätzliche belegte Vertragsverteilung',
            type: BusinessInput.choice,
            initial: d['thirty_day_rule'],
            choices: const {
              'actual_days_capped_per_claim': 'Belegt: tatsächliche Anspruchstage, höchstens 30, geteilt durch 30',
            },
          ),
          BusinessField(
            'policy_id',
            'Betriebliche Entscheidung für pauschal versteuerte Reisebeträge',
            type: BusinessInput.choice,
            initial: decision['policy_ref']?['id'],
            choices: {
              ...choices(
                businessItems(page['travel_tax_policies'])
                    .where((v) => v['status'] == 'active')
                    .toList(),
                (v) =>
                    '${businessDate(v['effective_from'])} – ${businessDate(v['effective_to'])} · ${payrollTravelChurchMethods[v['details']['church_method']]}',
                empty: false,
              ),
            },
          ),
          files(
            page,
            'source_file_ids',
            'Geschützte Originale für diesen Gesamtfall',
            initial: previous?['source_file_ids'],
          ),
          BusinessField(
            'verification_note',
            'Belegte Prüfung der gesamten Zuordnung',
            required: true,
            initial: d['verification_note'],
          ),
          if (previous != null)
            const BusinessField(
              'correction_reason',
              'Belegter Berichtigungsgrund',
              required: true,
            ),
        ],
      );
      if (values == null || opening != epoch) return;
      final count = values['event_count'];
      if (count is! int || count < 0 || count > 31)
        _fail('Die tatsächliche Anzahl von 0 bis 31 Profilwechseln angeben.');
      values['month'] = month;
      final outer = values['source_file_ids'];
      if (outer is! List || outer.isEmpty)
        _fail('Die konkreten geschützten Originale auswählen.');
      final originalPage = {
        ...page,
        'files': businessItems(page['files'])
            .where((v) => outer.contains(v['id']))
            .toList(),
      };
      final selectedProfiles = businessItems(page['profiles'])
          .where((v) => (values['profile_ids'] as List).contains(v['id']))
          .toList();
      final fields = <BusinessField>[];
      for (var i = 0; i < count; i++) {
        final old = i < oldEvents.length ? oldEvents[i] : <String, dynamic>{};
        fields.addAll([
          BusinessField(
            'event_${i}_kind',
            'Wechsel ${i + 1}: belegte Art',
            type: BusinessInput.choice,
            required: true,
            initial: old['kind'],
            choices: const {
              '': 'Bitte ausdrücklich auswählen',
              ...payrollCalculationEventKinds,
            },
          ),
          BusinessField(
            'event_${i}_date',
            'Wechsel ${i + 1}: wirksam ab',
            type: BusinessInput.date,
            required: true,
            initial: old['effective_from'],
          ),
          BusinessField(
            'event_${i}_before',
            'Wechsel ${i + 1}: Profil davor',
            type: BusinessInput.choice,
            required: true,
            initial: old['before_profile_ref']?['id'],
            choices: choices(
              selectedProfiles,
              (v) =>
                  '${businessDate(v['profile']?['effective_from'])} · Fassung ${v['revision']}',
            ),
          ),
          BusinessField(
            'event_${i}_after',
            'Wechsel ${i + 1}: Profil danach',
            type: BusinessInput.choice,
            required: true,
            initial: old['after_profile_ref']?['id'],
            choices: choices(
              selectedProfiles,
              (v) =>
                  '${businessDate(v['profile']?['effective_from'])} · Fassung ${v['revision']}',
            ),
          ),
          files(
            originalPage,
            'event_${i}_files',
            'Wechsel ${i + 1}: konkrete Originale',
            initial: old['source_file_ids'],
          ),
          BusinessField(
            'event_${i}_reason',
            'Wechsel ${i + 1}: belegter Grund',
            required: true,
            initial: old['reason'],
          ),
        ]);
      }
      final policy = businessItems(page['travel_tax_policies'])
          .where((v) => v['id'] == values['policy_id'])
          .firstOrNull;
      if (policy != null) {
        final membership = businessMap(decision['church_membership_evidence']);
        if (policy['details']['church_method'] == 'evidence')
          fields.addAll([
            BusinessField(
              'membership_kind',
              'Konkreter Nachweis der Kirchenzugehörigkeit',
              type: BusinessInput.choice,
              required: true,
              initial: membership['kind'],
              choices: const {
                '': 'Bitte ausdrücklich auswählen',
                ...payrollCalculationMembershipKinds,
              },
            ),
            BusinessField(
              'membership_identity_id',
              'ELStAM-/Ersatzbescheinigungsfassung, falls diese Nachweisart gewählt ist',
              type: BusinessInput.choice,
              initial: membership['reference']?['id'],
              choices: choices(
                page['identities'],
                (v) =>
                    '${businessDate(v['details']?['valid_from'])} – ${businessDate(v['details']?['valid_to'])} · Fassung ${v['revision']}',
                empty: false,
              ),
            ),
            files(
              originalPage,
              'membership_file_id',
              'Amtliche Erklärung oder dokumentierter allgemeiner Satz, falls diese Nachweisart gewählt ist',
              multiple: false,
              required: false,
              initial: membership['reference']?['id'],
            ),
            BusinessField(
              'membership_church',
              'Nachgewiesene Kirchensteuerzugehörigkeit',
              type: BusinessInput.choice,
              initial: membership['church_tax'] == true
                  ? 'yes'
                  : membership['church_tax'] == false
                  ? 'no'
                  : 'unknown',
              choices: const {
                'unknown': 'Ungeklärt: nur mit allgemeinem Satz und Nachweis',
                'yes': 'Kirchensteuerpflicht belegt',
                'no': 'Keine Kirchensteuerpflicht belegt',
              },
            ),
          ]);
        if (policy['details']['employer_bears_tax'] == false)
          fields.add(
            files(
              originalPage,
              'employee_deduction_file_id',
              'Ausdrückliche Arbeitnehmerzustimmung zum Steuerkostenabzug',
              multiple: false,
              initial: decision['employee_deduction_file_ref']?['id'],
            ),
          );
        fields.addAll([
          files(
            originalPage,
            'tax_certificate_file_id',
            'Bereits ausgestellte Lohnsteuerbescheinigung, falls vorhanden',
            multiple: false,
            required: false,
            initial: decision['tax_certificate_file_ref']?['id'],
          ),
          BusinessField(
            'tax_certificate_issued_on',
            'Tatsächliches Ausstellungsdatum nur bei vorhandener Bescheinigung',
            type: BusinessInput.date,
            initial: decision['tax_certificate_issued_on'],
          ),
          const BusinessField(
            'record_on_finalize',
            'Pauschalsteuer mit dem tatsächlichen Lohnabschluss erfassen.',
            type: BusinessInput.toggle,
          ),
        ]);
      }
      fields.add(
        const BusinessField(
          'confirmed',
          'Ich bestätige die vollständigen tatsächlichen Quellen und ihre Zuordnung.',
          type: BusinessInput.toggle,
        ),
      );
      final captured = session.generation;
      Map<String, dynamic>? nextBody, nextPreview;
      if (!mounted) return;
      await privateDialog<bool>(
        (_) => BusinessEditor(
          session: session,
          title: 'Konkrete Zuordnung prüfen',
          fields: fields,
          readPermission: 'personnel.read',
          writePermission: 'personnel.approve',
          readAllowed: () => readable && opening == epoch,
          saveLabel: 'Abrechnungsfall unverbindlich prüfen',
          onSave: (input) async {
            if (input['confirmed'] != true)
              _fail(
                'Die tatsächlichen Quellen und ihre Zuordnung ausdrücklich bestätigen.',
              );
            await fresh(write: true);
            if (captured != session.generation || opening != epoch)
              _fail(
                'Der freigegebene Quellenstand wurde geändert. Den Vorgang neu öffnen.',
                409,
              );
            final body = payrollCalculationCaseInput(employeeId, page, {
              ...values,
              ...input,
              'membership_church_tax': input['membership_church'] == 'yes'
                  ? true
                  : input['membership_church'] == 'no'
                  ? false
                  : null,
              'segment_events': [
                for (var i = 0; i < count; i++)
                  {
                    'kind': input['event_${i}_kind'],
                    'effective_from': input['event_${i}_date'],
                    'before_profile_id': input['event_${i}_before'],
                    'after_profile_id': input['event_${i}_after'],
                    'source_file_ids': input['event_${i}_files'],
                    'reason': input['event_${i}_reason'],
                  },
              ],
            }, previous: previous);
            nextPreview = payrollCalculationCasePreview(
              await session.api.call(
                session.path('/payroll/calculation-cases/preview'),
                payrollCalculationCasePreviewInput(body),
              ),
              body,
            );
            nextBody = {...body, 'preview_hash': nextPreview!['preview_hash']};
          },
        ),
      );
      if (mounted &&
          readable &&
          opening == epoch &&
          captured == session.generation &&
          nextPreview != null &&
          nextBody != null) {
        setState(() {
          sources = page;
          generation = session.generation;
          preview = nextPreview;
          previewBody = nextBody;
          correction = previous == null ? null : _copy(previous);
          selected = null;
          history = [];
        });
        showBeginning();
      }
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> editFactorClaims([
    Map<String, dynamic>? previous,
    bool includePaidTravel = false,
  ]) async {
    final combined =
        includePaidTravel ||
        previous?['rule_version'] == payrollFactorClaimTravelRule;
    final feature = combined
        ? payrollFactorClaimTravelFeature
        : payrollFactorClaimsFeature;
    final rule = combined
        ? payrollFactorClaimTravelRule
        : payrollFactorClaimsRule;
    if (busy || pending != null || !session.hasFeature(feature)) return;
    final opening = epoch;
    try {
      final page = await fresh(write: true);
      if (!mounted ||
          !readable ||
          opening != epoch ||
          !session.hasFeature(feature))
        return;
      final d = businessMap(previous?['details']);
      final values = await choose(
        combined
            ? 'Faktor-Monat mit Ansprüchen und bezahlten Reisen'
            : previous == null
            ? 'Faktor-Monat mit belegten Lohnansprüchen'
            : 'Faktor-Anspruchsfall berichtigen',
        [
          BusinessField(
            'period_case_id',
            'Bestätigter voller Faktor-Monat',
            type: BusinessInput.choice,
            required: true,
            initial: d['period_case_ref']?['id'],
            choices: choices(
              businessItems(page['factor_period_facts'])
                  .where(
                    (v) =>
                        payrollFactorClaimsBaseEligible(v, month) &&
                        v['details']['month'] == month,
                  )
                  .toList(),
              (v) => '${v['details']['month']} · Fassung ${v['revision']}',
            ),
          ),
          BusinessField(
            'employment_terms_ids',
            'Eine bestätigte Beschäftigungsepisode',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['employment_terms_refs']),
            choices: choices(
              businessItems(page['facts'])
                  .where(
                    (v) =>
                        v['kind'] == 'employment_terms' &&
                        v['status'] == 'active',
                  )
                  .toList(),
              (v) =>
                  '${businessDate(v['effective_from'])} – ${businessDate(v['effective_to'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'profile_ids',
            'Ein bestätigtes Faktor-/SV-Profil',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['profile_refs']),
            choices: choices(
              page['profiles'],
              (v) =>
                  '${businessDate(v['profile']?['effective_from'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'identity_ids',
            'Ein zugehöriger Identitäts-/Steuernachweis',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['identity_refs']),
            choices: choices(
              page['identities'],
              (v) =>
                  '${businessDate(v['details']?['valid_from'])} – ${businessDate(v['details']?['valid_to'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'entitlement_case_ids',
            'Alle aktiven Anspruchsnachweise im Monat',
            type: BusinessInput.multiple,
            required: true,
            initial: businessItems(page['entitlements'])
                .where(
                  (v) =>
                      v['status'] == 'active' &&
                      v['effective_from'].compareTo(
                            payrollFactDates(month).last,
                          ) <=
                          0 &&
                      v['effective_to'].compareTo(
                            payrollFactDates(month).first,
                          ) >=
                          0,
                )
                .map((v) => v['id'])
                .toList(),
            choices: choices(
              businessItems(page['entitlements'])
                  .where((v) => v['status'] == 'active')
                  .toList(),
              (v) =>
                  '${businessDate(v['effective_from'])} – ${businessDate(v['effective_to'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          if (combined)
            BusinessField(
              'travel_settlement_ids',
              'Bereits erstattete steuerfreie Reiseabrechnungen',
              type: BusinessInput.multiple,
              required: true,
              initial: ids(d['travel_settlement_refs']),
              choices: choices(
                businessItems(page['travel_settlements'])
                    .where((v) => v['status'] == 'approved')
                    .toList(),
                (v) =>
                    'Reise · Fassung ${v['revision']} · ${businessDate(v['created_at'])}',
                empty: false,
              ),
            ),
          if (combined)
            BusinessField(
              'travel_payment_ids',
              'Tatsächliche Auszahlungs- und Rückzahlungsnachweise',
              type: BusinessInput.multiple,
              required: true,
              initial: ids(d['travel_payment_refs']),
              choices: choices(
                page['travel_payment_proofs'],
                (v) =>
                    '${businessDate(v['paid_on'])} · ${v['kind'] == 'repayment' ? 'Rückzahlung' : 'Erstattung'} · ${_money(v['amount_minor'])} · Fassung ${v['revision']}',
                empty: false,
              ),
            ),
          if (combined &&
              previous != null &&
              previous['rule_version'] != payrollFactorClaimTravelRule)
            const BusinessField(
              'confirm_unused_upgrade',
              'Ich ergänze nur den fehlenden Bestandteil eines bisher unbenutzten ursprünglichen Faktorfalls.',
              type: BusinessInput.toggle,
            ),
          files(
            page,
            'source_file_ids',
            'Geschützte Originale für diesen Gesamtfall',
            initial: previous?['source_file_ids'],
          ),
          BusinessField(
            'verification_note',
            'Belegte Prüfung der gesamten Zuordnung',
            required: true,
            initial: d['verification_note'],
          ),
          if (previous != null)
            const BusinessField(
              'correction_reason',
              'Belegter Berichtigungsgrund',
              required: true,
            ),
          BusinessField(
            'confirmed',
            combined
                ? 'Ich bestätige den vollständigen Faktor-Monat, alle belegten Lohnansprüche und die bereits getrennt erstatteten steuerfreien Reisen.'
                : 'Ich bestätige den vollständigen Faktor-Monat und sämtliche belegten Lohnansprüche aus den ausgewählten Originalen.',
            type: BusinessInput.toggle,
          ),
        ],
        saveLabel: combined
            ? 'Faktor-/Anspruchs-/Reisefall unverbindlich prüfen'
            : 'Faktor-Anspruchsfall unverbindlich prüfen',
      );
      if (values == null || opening != epoch) return;
      if (values['confirmed'] != true)
        _fail(
          'Den vollständigen Faktor-Monat und seine belegten Lohnansprüche ausdrücklich bestätigen.',
        );
      await fresh(write: true);
      if (!mounted ||
          !readable ||
          opening != epoch ||
          !session.hasFeature(feature))
        return;
      final body = payrollCalculationCaseInput(employeeId, page, {
        ...values,
        'month': month,
        'rule_version': rule,
        'segment_events': <Map<String, dynamic>>[],
        if (!combined) 'travel_settlement_ids': <String>[],
        'thirty_day_rule': null,
        'policy_id': null,
      }, previous: previous);
      final result = payrollCalculationCasePreview(
        await session.api.call(
          session.path('/payroll/calculation-cases/preview'),
          payrollCalculationCasePreviewInput(body),
        ),
        body,
      );
      if (!mounted || !readable || opening != epoch) return;
      setState(() {
        sources = page;
        generation = session.generation;
        previewBody = {...body, 'preview_hash': result['preview_hash']};
        preview = result;
        correction = previous == null ? null : _copy(previous);
        selected = null;
        history = [];
      });
      showBeginning();
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> editFactorTransition([
    Map<String, dynamic>? previous,
    bool partial = false,
  ]) async {
    final feature = partial
        ? payrollFactorTransitionPeriodFeature
        : payrollFactorTransitionFeature;
    if (busy || pending != null || !session.hasFeature(feature)) return;
    final opening = epoch;
    try {
      final page = await fresh(write: true);
      if (!mounted ||
          !readable ||
          opening != epoch ||
          !session.hasFeature(feature))
        return;
      final d = businessMap(previous?['details']),
          review = businessMap(
            previous?['details']?[partial
                ? 'factor_transition_period_assessment'
                : 'factor_transition_assessment'],
          );
      final forecast = businessMap(review['transition_assessment']);
      final fields = <BusinessField>[
        BusinessField(
          'period_case_id',
          partial
              ? 'Bestätigter Faktor-Teilmonat mit 30-Tage-Vertrag'
              : 'Bestätigter vollständiger Faktor-Monat',
          type: BusinessInput.choice,
          required: true,
          initial: d['period_case_ref']?['id'],
          choices: choices(
            businessItems(page['factor_period_facts'])
                .where(
                  (v) => partial
                      ? payrollFactorTransitionPeriodSelectable(v, month)
                      : payrollFactorClaimsBaseEligible(v, month),
                )
                .toList(),
            (v) => '${v['details']['month']} · Fassung ${v['revision']}',
          ),
        ),
        BusinessField(
          'employment_terms_ids',
          'Eine belegte Beschäftigung',
          type: BusinessInput.multiple,
          required: true,
          initial: ids(d['employment_terms_refs']),
          choices: choices(
            businessItems(page['facts'])
                .where(
                  (v) =>
                      v['kind'] == 'employment_terms' &&
                      v['status'] == 'active',
                )
                .toList(),
            (v) =>
                '${businessDate(v['effective_from'])} · Fassung ${v['revision']}',
            empty: false,
          ),
        ),
        BusinessField(
          'profile_ids',
          'Ein ursprüngliches ELStAM-Faktorprofil',
          type: BusinessInput.multiple,
          required: true,
          initial: ids(d['profile_refs']),
          choices: choices(
            page['profiles'],
            (v) =>
                '${businessDate(v['profile']['effective_from'])} · Fassung ${v['revision']}',
            empty: false,
          ),
        ),
        BusinessField(
          'identity_ids',
          'Ein passender Identitäts- und ELStAM-Nachweis',
          type: BusinessInput.multiple,
          required: true,
          initial: ids(d['identity_refs']),
          choices: choices(
            page['identities'],
            (v) =>
                '${businessDate(v['details']['valid_from'])} – ${businessDate(v['details']['valid_to'])} · Fassung ${v['revision']}',
            empty: false,
          ),
        ),
        BusinessField(
          'valid_from',
          'Prognose gültig ab',
          type: BusinessInput.date,
          required: true,
          initial: review['valid_from'],
        ),
        BusinessField(
          'valid_to',
          'Prognose gültig bis',
          type: BusinessInput.date,
          required: true,
          initial: review['valid_to'],
        ),
        BusinessField(
          'declaration_date',
          'Tatsächlicher Tag der Prüfung',
          type: BusinessInput.date,
          required: true,
          initial: review['declaration_date'],
        ),
        BusinessField(
          'assessed_on',
          'Tag der ursprünglichen Statusprognose',
          type: BusinessInput.date,
          required: true,
          initial: forecast['assessed_on'],
        ),
        BusinessField(
          'regular_monthly_gross',
          'Belegter fester regelmäßiger Monatslohn in EUR',
          type: BusinessInput.decimal,
          required: true,
          initial: forecast['regular_monthly_gross_minor'] is int
              ? ((forecast['regular_monthly_gross_minor'] as int) / 100)
                    .toStringAsFixed(2)
              : null,
        ),
        BusinessField(
          'forecast_months',
          'Belegter Prognosezeitraum in Monaten',
          type: BusinessInput.integer,
          required: true,
          initial: forecast['forecast_months'],
        ),
        files(
          page,
          'forecast_file_id',
          'Konkretes privates Prognoseoriginal',
          multiple: false,
          initial: review['forecast_evidence_ref']?['id'],
        ),
        files(
          page,
          'source_file_ids',
          'Gebundene private Originale',
          initial: previous?['source_file_ids'],
        ),
        const BusinessField(
          'sole_employment_confirmed',
          'Alleinige Beschäftigung und tatsächlichen Übergangsbereich geprüft',
          type: BusinessInput.toggle,
        ),
        BusinessField(
          partial
              ? 'fixed_monthly_contract_confirmed'
              : 'full_fixed_monthly_pay_confirmed',
          partial ? 'Unveränderten festen Monatsvertrag geprüft' : 'Unveränderten festen Monatslohn für diesen vollständigen Monat geprüft',
          type: BusinessInput.toggle,
        ),
        if (partial)
          const BusinessField(
            'contractual_30_days_confirmed',
            'Belegte Teilentgeltmethode: tatsächliche Anspruchstage, höchstens 30, geteilt durch 30',
            type: BusinessInput.toggle,
          ),
        const BusinessField(
          'no_foreseeable_one_off_confirmed',
          'Keine vorhersehbaren Einmalbezüge in dieser Prognose',
          type: BusinessInput.toggle,
        ),
        BusinessField(
          'forecast_note',
          'Belegte Grundlage der Zwölfmonatsprognose',
          required: true,
          initial: forecast['note'],
        ),
        BusinessField(
          'assessment_note',
          'Ergebnis der personenbezogenen Prüfung',
          required: true,
          initial: review['verification_note'],
        ),
        BusinessField(
          'verification_note',
          'Prüfvermerk zum gesamten Abrechnungsfall',
          required: true,
          initial: d['verification_note'],
        ),
        if (previous != null)
          const BusinessField(
            'correction_reason',
            'Belegter Korrekturgrund',
            required: true,
          ),
      ];
      final values = await choose(
        previous == null
            ? partial
                  ? 'Midijob-Teilmonat mit belegtem ELStAM-Faktor'
                  : 'Midijob mit belegtem ELStAM-Faktor'
            : partial
            ? 'Faktor-Midijob-Teilmonat berichtigen'
            : 'Faktor-Midijob berichtigen',
        fields,
        saveLabel: partial
            ? 'Faktor-Midijob-Teilmonat unverbindlich prüfen'
            : 'Faktor-Midijob unverbindlich prüfen',
      );
      if (values == null || opening != epoch) return;
      for (final key in [
        'sole_employment_confirmed',
        partial
            ? 'fixed_monthly_contract_confirmed'
            : 'full_fixed_monthly_pay_confirmed',
        if (partial) 'contractual_30_days_confirmed',
        'no_foreseeable_one_off_confirmed',
      ])
        if (values[key] != true)
          _fail(
            'Die tatsächliche vollständige Prognose ohne weitere Beschäftigung oder Einmalbezüge bestätigen.',
          );
      await fresh(write: true);
      if (!mounted ||
          !readable ||
          opening != epoch ||
          !session.hasFeature(feature))
        return;
      final raw = '${values['regular_monthly_gross']}'.trim().replaceAll(
        ',',
        '.',
      );
      if (!RegExp(r'^\d{1,4}(?:\.\d{1,2})?$').hasMatch(raw))
        _fail('Den genauen belegten Monatslohn in Euro angeben.');
      final parts = raw.split('.'),
          amount =
              int.parse(parts.first) * 100 +
              int.parse((parts.length == 1 ? '' : parts.last).padRight(2, '0'));
      final originals = businessItems(page['files'])
          .where((v) => v['id'] == values['forecast_file_id'])
          .toList();
      if (originals.length != 1)
        _fail('Das konkrete eigene Prognoseoriginal auswählen.');
      final original = originals.single;
      final assessment = {
        'schema_version': 1,
        'employee_id': employeeId,
        'valid_from': values['valid_from'],
        'valid_to': values['valid_to'],
        'declaration_date': values['declaration_date'],
        'transition_assessment': {
          'status': 'within_transition_area',
          'assessed_on': values['assessed_on'],
          'regular_monthly_gross_minor': amount,
          'forecast_months': values['forecast_months'],
          'foreseeable_one_off_payments': false,
          'note': values['forecast_note'],
        },
        'forecast_evidence_ref': {
          'id': original['id'],
          'revision': 1,
          'content_hash': original['content_hash'],
        },
        'sole_employment_confirmed': values['sole_employment_confirmed'],
        if (!partial)
          'full_fixed_monthly_pay_confirmed':
              values['full_fixed_monthly_pay_confirmed'],
        if (partial)
          'fixed_monthly_contract_confirmed':
              values['fixed_monthly_contract_confirmed'],
        if (partial)
          'contractual_30_days_confirmed':
              values['contractual_30_days_confirmed'],
        'verification_note': values['assessment_note'],
      };
      final body = payrollCalculationCaseInput(employeeId, page, {
        ...values,
        'month': month,
        'rule_version': partial
            ? payrollFactorTransitionPeriodRule
            : payrollFactorTransitionRule,
        (partial
                ? 'factor_transition_period_assessment'
                : 'factor_transition_assessment'):
            assessment,
      }, previous: previous);
      final result = payrollCalculationCasePreview(
        await session.api.call(
          session.path('/payroll/calculation-cases/preview'),
          payrollCalculationCasePreviewInput(body),
        ),
        body,
      );
      if (!mounted || !readable || opening != epoch) return;
      setState(() {
        sources = page;
        generation = session.generation;
        previewBody = {...body, 'preview_hash': result['preview_hash']};
        preview = result;
        correction = previous == null ? null : _copy(previous);
        selected = null;
        history = [];
      });
      showBeginning();
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> editFactorTravel([Map<String, dynamic>? previous]) async {
    if (busy ||
        pending != null ||
        !session.hasFeature('payroll_factor_taxfree_travel'))
      return;
    final opening = epoch;
    try {
      final page = await fresh(write: true);
      if (!mounted ||
          !readable ||
          opening != epoch ||
          !session.hasFeature('payroll_factor_taxfree_travel'))
        return;
      final d = businessMap(previous?['details']);
      final values = await choose(
        previous == null
            ? 'Faktor-Vollmonat mit bezahlter steuerfreier Reise'
            : 'Faktor-Reisefall berichtigen',
        [
          BusinessField(
            'period_case_id',
            'Bestätigter voller Faktor-Monat',
            type: BusinessInput.choice,
            required: true,
            initial: d['period_case_ref']?['id'],
            choices: choices(
              businessItems(page['factor_period_facts'])
                  .where(
                    (v) =>
                        payrollFactorTravelBaseEligible(v) &&
                        v['details']['month'] == month,
                  )
                  .toList(),
              (v) => '${v['details']['month']} · Fassung ${v['revision']}',
            ),
          ),
          BusinessField(
            'employment_terms_ids',
            'Eine bestätigte Beschäftigungsepisode',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['employment_terms_refs']),
            choices: choices(
              businessItems(page['facts'])
                  .where(
                    (v) =>
                        v['kind'] == 'employment_terms' &&
                        v['status'] == 'active',
                  )
                  .toList(),
              (v) =>
                  '${businessDate(v['effective_from'])} – ${businessDate(v['effective_to'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'profile_ids',
            'Ein bestätigtes Faktor-/SV-Profil',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['profile_refs']),
            choices: choices(
              page['profiles'],
              (v) =>
                  '${businessDate(v['profile']?['effective_from'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'identity_ids',
            'Ein zugehöriger Identitäts-/Steuernachweis',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['identity_refs']),
            choices: choices(
              page['identities'],
              (v) =>
                  '${businessDate(v['details']?['valid_from'])} – ${businessDate(v['details']?['valid_to'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          BusinessField(
            'travel_settlement_ids',
            'Bereits erstattete steuerfreie Reiseabrechnungen',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['travel_settlement_refs']),
            choices: choices(
              businessItems(page['travel_settlements'])
                  .where((v) => v['status'] == 'approved')
                  .toList(),
              (v) =>
                  'Reise · Fassung ${v['revision']} · ${businessDate(v['created_at'])}',
              empty: false,
            ),
          ),
          BusinessField(
            'travel_payment_ids',
            'Tatsächliche Auszahlungs- und Rückzahlungsnachweise',
            type: BusinessInput.multiple,
            required: true,
            initial: ids(d['travel_payment_refs']),
            choices: choices(
              page['travel_payment_proofs'],
              (v) =>
                  '${businessDate(v['paid_on'])} · ${v['kind'] == 'repayment' ? 'Rückzahlung' : 'Erstattung'} · ${_money(v['amount_minor'])} · Fassung ${v['revision']}',
              empty: false,
            ),
          ),
          files(
            page,
            'source_file_ids',
            'Geschützte Originale für diesen Gesamtfall',
            initial: previous?['source_file_ids'],
          ),
          BusinessField(
            'verification_note',
            'Belegte Prüfung der gesamten Zuordnung',
            required: true,
            initial: d['verification_note'],
          ),
          if (previous != null)
            const BusinessField(
              'correction_reason',
              'Belegter Berichtigungsgrund',
              required: true,
            ),
          const BusinessField(
            'confirmed',
            'Ich bestätige den vollen Faktor-Monat und die bereits vollständig außerhalb des Lohns erstatteten steuerfreien Reisen.',
            type: BusinessInput.toggle,
          ),
        ],
        saveLabel: 'Faktor-Reisefall unverbindlich prüfen',
      );
      if (values == null || opening != epoch) return;
      if (values['confirmed'] != true)
        _fail(
          'Den begrenzten Faktor-Monat und die tatsächliche Erstattung ausdrücklich bestätigen.',
        );
      await fresh(write: true);
      if (!mounted ||
          !readable ||
          opening != epoch ||
          !session.hasFeature('payroll_factor_taxfree_travel'))
        return;
      final body = payrollCalculationCaseInput(employeeId, page, {
        ...values,
        'month': month,
        'rule_version': payrollFactorTaxfreeTravelRule,
        'segment_events': <Map<String, dynamic>>[],
        'entitlement_case_ids': <String>[],
        'thirty_day_rule': null,
        'policy_id': null,
      }, previous: previous);
      final result = payrollCalculationCasePreview(
        await session.api.call(
          session.path('/payroll/calculation-cases/preview'),
          payrollCalculationCasePreviewInput(body),
        ),
        body,
      );
      if (!mounted || !readable || opening != epoch) return;
      setState(() {
        sources = page;
        generation = session.generation;
        previewBody = {...body, 'preview_hash': result['preview_hash']};
        preview = result;
        correction = previous == null ? null : _copy(previous);
        selected = null;
        history = [];
      });
      showBeginning();
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> editIndividualMinijob([Map<String, dynamic>? previous]) async {
    if (busy ||
        pending != null ||
        !session.hasFeature(individualMinijobFeature))
      return;
    final opening = epoch;
    try {
      final page = await fresh(write: true);
      if (!mounted ||
          !readable ||
          opening != epoch ||
          !session.hasFeature(individualMinijobFeature))
        return;
      final details = businessMap(previous?['details']);
      final assessment = businessMap(details['individual_minijob_assessment']);
      final dates = payrollFactDates(month);
      final converted =
          previous != null && previous['rule_version'] != individualMinijobRule;
      final values = await choose(
        converted
            ? 'Gesperrten Altfall ausdrücklich neu prüfen'
            : previous == null
            ? 'Individuellen Minijob belegt prüfen'
            : 'Individuellen Minijob berichtigen',
        [
          BusinessField(
            'period_case_id',
            'Bestätigter Basisfall des vollen Monats',
            type: BusinessInput.choice,
            required: true,
            initial: details['period_case_ref']?['id'],
            choices: choices(
              businessItems(page['facts'])
                  .where(
                    (v) =>
                        v['kind'] == 'period_case' &&
                        v['status'] == 'active' &&
                        v['details']['month'] == month,
                  )
                  .toList(),
              (v) => '${v['details']['month']} · Fassung ${v['revision']}',
            ),
          ),
          BusinessField(
            'employment_terms_id',
            'Eine belegte Beschäftigungsepisode',
            type: BusinessInput.choice,
            required: true,
            initial:
                (details['employment_terms_refs'] as List?)?.firstOrNull?['id'],
            choices: choices(
              businessItems(page['facts'])
                  .where(
                    (v) =>
                        v['kind'] == 'employment_terms' &&
                        v['status'] == 'active',
                  )
                  .toList(),
              (v) =>
                  '${businessDate(v['effective_from'])} – ${businessDate(v['effective_to'])} · Fassung ${v['revision']}',
            ),
          ),
          BusinessField(
            'profile_id',
            'Tatsächliches individuelles Minijobprofil',
            type: BusinessInput.choice,
            required: true,
            initial: (details['profile_refs'] as List?)?.firstOrNull?['id'],
            choices: choices(
              businessItems(page['profiles'])
                  .where(
                    (v) =>
                        v['profile']?['employment_kind'] == 'minijob' &&
                        v['profile']?['minijob_tax'] == 'individual' &&
                        v['profile']?['health_insurance'] == 'statutory_other',
                  )
                  .toList(),
              (v) =>
                  '${businessDate(v['profile']['effective_from'])} · Fassung ${v['revision']}',
            ),
          ),
          BusinessField(
            'identity_id',
            'ELStAM-Identitätsnachweis für individuellen Minijob',
            type: BusinessInput.choice,
            required: true,
            initial: (details['identity_refs'] as List?)?.firstOrNull?['id'],
            choices: choices(
              businessItems(page['identities'])
                  .where(
                    (v) => v['details']?['identity_source_schema_version'] == 2,
                  )
                  .toList(),
              (v) =>
                  '${businessDate(v['details']['valid_from'])} · Fassung ${v['revision']}',
            ),
          ),
          BusinessField(
            'valid_from',
            'Prüfung gilt ab',
            type: BusinessInput.date,
            required: true,
            initial: assessment['valid_from'] ?? dates.first,
          ),
          BusinessField(
            'valid_to',
            'Prüfung gilt bis',
            type: BusinessInput.date,
            required: true,
            initial: assessment['valid_to'] ?? dates.last,
          ),
          BusinessField(
            'declaration_date',
            'Tatsächliches Datum der persönlichen Prüfung',
            type: BusinessInput.date,
            required: true,
            initial: assessment['declaration_date'],
          ),
          BusinessField(
            'actual_health_insurance',
            'Tatsächliche Krankenversicherung',
            type: BusinessInput.choice,
            required: true,
            initial: assessment['actual_health_insurance'],
            choices: const {
              'statutory_family':
                  'Beitragsfreie gesetzliche Familienversicherung',
              'statutory_mandatory':
                  'Gesetzlich pflichtversichert · gesperrter Umfang',
              'statutory_voluntary':
                  'Gesetzlich freiwillig versichert · gesperrter Umfang',
              'private': 'Privat versichert · gesperrter Umfang',
              'unknown': 'Noch nicht belegt · gesperrter Umfang',
            },
          ),
          BusinessField(
            'pension_status',
            'Belegter Rentenversicherungsstatus',
            type: BusinessInput.choice,
            required: true,
            initial: assessment['pension_status'],
            choices: const {
              'compulsory': 'Rentenversicherungspflichtig',
              'exempt': 'Wirksam von der RV-Pflicht befreit',
              'unknown': 'Noch nicht belegt · gesperrter Umfang',
            },
          ),
          for (final entry in individualMinijobConfirmations.entries)
            BusinessField(
              entry.key,
              entry.value,
              type: BusinessInput.toggle,
              initial: assessment[entry.key] == true,
            ),
          for (final entry in individualMinijobEvidence.entries)
            files(
              page,
              '${entry.key}_id',
              entry.value,
              multiple: false,
              initial: assessment[entry.key]?['id'],
            ),
          files(
            page,
            'source_file_ids',
            'Weitere geschützte Originale',
            required: false,
            initial: previous?['source_file_ids'],
          ),
          BusinessField(
            'assessment_note',
            'Persönliche Prüfung und Belegzuordnung',
            required: true,
            initial: assessment['verification_note'],
          ),
          BusinessField(
            'verification_note',
            'Prüfung des gesamten Minijobfalls',
            required: true,
            initial: details['verification_note'],
          ),
          if (previous != null)
            const BusinessField(
              'correction_reason',
              'Ausdrücklicher Korrekturgrund',
              required: true,
            ),
          BusinessField(
            'confirmed',
            converted
                ? 'Ich beauftrage die ausdrückliche Neubeurteilung des gesperrten Altfalls; alle Originale bleiben erhalten.'
                : 'Ich bestätige ausschließlich diesen belegten individuellen Minijobfall.',
            type: BusinessInput.toggle,
          ),
        ],
        saveLabel: 'Individuellen Minijob unverbindlich prüfen',
      );
      if (values == null || opening != epoch) return;
      if (values['confirmed'] != true)
        _fail('Die persönliche Prüfung ausdrücklich bestätigen.');
      await fresh(write: true);
      if (!mounted ||
          !readable ||
          opening != epoch ||
          !session.hasFeature(individualMinijobFeature))
        return;
      final selectedFiles = <String>{
        ...List<String>.from(values['source_file_ids'] as List? ?? []),
        for (final key in individualMinijobEvidence.keys)
          values['${key}_id'] as String,
      };
      final body = payrollCalculationCaseInput(employeeId, page, {
        ...values,
        'source_file_ids': selectedFiles.toList(),
        'month': month,
        'rule_version': individualMinijobRule,
      }, previous: previous);
      final result = payrollCalculationCasePreview(
        await session.api.call(
          session.path('/payroll/calculation-cases/preview'),
          payrollCalculationCasePreviewInput(body),
        ),
        body,
      );
      if (!mounted || !readable || opening != epoch) return;
      setState(() {
        sources = page;
        generation = session.generation;
        preview = result;
        previewBody = {...body, 'preview_hash': result['preview_hash']};
        correction = previous == null ? null : _copy(previous);
        selected = null;
        history = [];
      });
      showBeginning();
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> confirm() async {
    if (preview == null || previewBody == null || !writable || pending != null)
      return;
    final proof = _copy(preview!),
        body = _copy(previewBody!),
        prior = correction == null ? null : _copy(correction!);
    final opening = epoch;
    final accepted = await privateDialog<bool>(
      (context) => AlertDialog(
        title: const Text('Geprüften Abrechnungsfall festhalten'),
        content: const Text(
          'Ich bestätige genau diesen geprüften Gesamtfall mit seinen Originalen.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Abrechnungsfall festhalten'),
          ),
        ],
      ),
    );
    if (accepted != true || !mounted || !readable || opening != epoch) return;
    await act(() => save(body, previous: prior, proof: proof));
  }

  Future<void> cancel(Map<String, dynamic> fact) async {
    if (pending != null) return;
    final opening = epoch;
    try {
      await fresh(write: true);
      if (!mounted || !readable || opening != epoch) return;
      final values = await choose(
        'Fälschlichen Abrechnungsfall aufheben',
        const [
          BusinessField(
            'correction_reason',
            'Belegter Aufhebungsgrund',
            required: true,
          ),
          BusinessField(
            'confirmed',
            'Ich bestätige die Aufhebung. Frühere Abrechnungen bleiben unverändert.',
            type: BusinessInput.toggle,
          ),
        ],
        saveLabel: 'Aufhebung prüfen',
      );
      if (values == null || !mounted || !readable || opening != epoch) return;
      if (values['confirmed'] != true)
        _fail('Die Aufhebung ausdrücklich bestätigen.');
      await act(() async {
        final page = await fresh(write: true);
        await save({
          'employee_id': employeeId,
          'employee_revision': page['employee']['revision'],
          'kind': 'calculation_case',
          'rule_version': fact['rule_version'],
          'source_contract_version': fact['source_contract_version'],
          'id': fact['id'],
          'revision': fact['revision'],
          'status': 'void',
          'details': _copy(fact['details']),
          'source_file_ids': List<String>.from(fact['source_file_ids']),
          'preview_hash': fact['preview_hash'],
          'correction_reason': values['correction_reason'],
          'confirmed': true,
        }, previous: fact);
      });
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> showHistory(Map<String, dynamic> fact) => act(() async {
    await fresh();
    final captured = epoch,
        page = businessMap(
          await session.read(
            '/payroll/calculation-cases/${fact['id']}/history',
          ),
        );
    if (page['items'] is! List)
      _fail('Die Abrechnungsfallhistorie fehlt.', 502);
    final items = businessItems(page['items']);
    if (items.isEmpty ||
        items.indexed.any(
          (entry) =>
              payrollCalculationCaseRecord(entry.$2, employeeId)['id'] !=
                  fact['id'] ||
              entry.$2['revision'] != entry.$1 + 1,
        ))
      _fail('Die Historie gehört nicht zum gewählten Abrechnungsfall.', 502);
    if (mounted && readable && captured == epoch)
      setState(() => history = items);
  });
  Widget recordView(Map<String, dynamic> value) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Abrechnungsfall ${value['details']['month']} · Fassung ${value['revision']}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text(
            value['status'] == 'active'
                ? 'Aktiver belegter Abrechnungsfall'
                : 'Abrechnungsfall aufgehoben; Historie bleibt erhalten.',
          ),
          Text('${value['details']['verification_note']}'),
          if ('${value['correction_reason'] ?? ''}'.isNotEmpty)
            Text('Berichtigungsgrund: ${value['correction_reason']}'),
          PayrollCalculationCasePlanView(
            plan: businessMap(value['plan']),
            sources: businessMap(value['sources']),
          ),
          if (!historical &&
              individualMinijobCanConvert(value) &&
              writable &&
              pending == null &&
              session.hasFeature(individualMinijobFeature))
            OutlinedButton(
              onPressed: busy ? null : () => editIndividualMinijob(value),
              child: const Text(
                'Gesperrten Minijob ausdrücklich neu beurteilen',
              ),
            ),
          for (final file in businessItems(value['sources']['source_files']))
            TextButton(
              onPressed: busy
                  ? null
                  : () => act(() async {
                      await fresh();
                      await widget.onOriginal(file);
                    }),
              child: Text('Personaloriginal: ${file['filename']}'),
            ),
          if (!historical)
            OutlinedButton(
              onPressed: busy ? null : () => showHistory(value),
              child: const Text('Abrechnungsfallhistorie öffnen'),
            ),
          if (!historical &&
              value['status'] == 'active' &&
              writable &&
              pending == null)
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                if (value['plan']['can_calculate'] == true)
                  FilledButton(
                    onPressed: busy
                        ? null
                        : () => act(() async {
                            await fresh(write: true);
                            await widget.onCalculate(_copy(value));
                          }),
                    child: const Text('Lohn aus diesem Gesamtfall berechnen'),
                  ),
                if ([
                      payrollFactorClaimsRule,
                      payrollFactorTaxfreeTravelRule,
                    ].contains(value['rule_version']) &&
                    session.hasFeature(payrollFactorClaimTravelFeature))
                  OutlinedButton(
                    onPressed: busy
                        ? null
                        : () => editFactorClaims(value, true),
                    child: const Text(
                      'Fehlenden Anspruchs- oder Reisebestandteil belegt ergänzen',
                    ),
                  ),
                OutlinedButton(
                  onPressed: busy ? null : () => edit(value),
                  child: const Text('Abrechnungsfall berichtigen'),
                ),
                OutlinedButton(
                  onPressed: busy ? null : () => cancel(value),
                  child: const Text('Fälschlichen Abrechnungsfall aufheben'),
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
      title: Text('Belegte Abrechnungsfälle · ${widget.employee['name']}'),
      actions: [
        IconButton(
          tooltip: 'Rechte und Quellen aktualisieren',
          onPressed: busy || loading ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !readable
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: BusinessEmpty(
              'Abrechnungsfälle nicht freigegeben',
              'Diese privaten Nachweise benötigen aktuelle globale Personal-Leserechte.',
            ),
          )
        : ListView(
            controller: pageScroll,
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Beschäftigungszeiträume, Ansprüche, Unterbrechungen und Reisebeträge werden anhand ihrer bestätigten Originale zusammengeführt.',
              ),
              if (error != null) Notice(error!, error: true),
              if (loading || busy) const LinearProgressIndicator(),
              Wrap(
                spacing: 12,
                runSpacing: 8,
                children: [
                  OutlinedButton(
                    onPressed: busy || pending != null ? null : chooseMonth,
                    child: Text('Monat $month wählen'),
                  ),
                  OutlinedButton(
                    onPressed: busy ? null : policies,
                    child: const Text('Betriebliche Reise-Steuerentscheidung'),
                  ),
                ],
              ),
              if (pending != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Bestätigung des Abrechnungsfalls offen'),
                        const Notice(
                          'Der ursprüngliche Auftrag kann bereits gespeichert sein. Seine Wiederholung verwendet dieselben Werte und dieselbe Vorgangskennung.',
                        ),
                        if (permitted)
                          FilledButton(
                            onPressed: busy ? null : repeat,
                            child: const Text(
                              'Ursprünglichen Abrechnungsauftrag erneut senden',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              if (preview != null) ...[
                Text(
                  'Abrechnungsfall prüfen',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                PayrollCalculationCasePlanView(
                  plan: businessMap(preview!['plan']),
                  sources: businessMap(preview!['source_snapshot']),
                ),
                if (preview!['can_confirm'] == true &&
                    writable &&
                    pending == null)
                  FilledButton(
                    onPressed: busy ? null : confirm,
                    child: const Text('Geprüften Abrechnungsfall festhalten'),
                  ),
              ],
              if (selected != null) recordView(selected!),
              for (final old in history)
                ListTile(
                  title: Text(
                    'Fassung ${old['revision']} · ${old['status'] == 'active' ? 'aktiv' : 'aufgehoben'}',
                  ),
                  subtitle: Text('${old['correction_reason'] ?? ''}'),
                  onTap: busy ? null : () => act(() => inspect(old, old: true)),
                ),
              if (sources != null) ...[
                if (writable &&
                    pending == null &&
                    session.hasFeature(payrollFactorTransitionFeature))
                  FilledButton.icon(
                    onPressed: busy ? null : () => editFactorTransition(),
                    icon: const Icon(Icons.fact_check_outlined),
                    label: const Text('Midijob mit belegtem ELStAM-Faktor'),
                  ),
                if (writable &&
                    pending == null &&
                    session.hasFeature(payrollFactorTransitionPeriodFeature))
                  FilledButton.icon(
                    onPressed: busy
                        ? null
                        : () => editFactorTransition(null, true),
                    icon: const Icon(Icons.fact_check_outlined),
                    label: const Text(
                      'Midijob-Teilmonat mit belegtem ELStAM-Faktor',
                    ),
                  ),
                if (writable &&
                    pending == null &&
                    session.hasFeature(individualMinijobFeature))
                  FilledButton.icon(
                    onPressed: busy ? null : () => editIndividualMinijob(),
                    icon: const Icon(Icons.fact_check_outlined),
                    label: const Text('Individuellen Minijob belegt prüfen'),
                  ),
                if (writable && pending == null)
                  FilledButton.icon(
                    onPressed: busy ? null : () => edit(),
                    icon: const Icon(Icons.add),
                    label: const Text(
                      'Belegten Abrechnungsfall zusammenstellen',
                    ),
                  ),
                if (writable &&
                    pending == null &&
                    session.hasFeature(payrollFactorClaimTravelFeature))
                  FilledButton.icon(
                    onPressed: busy ? null : () => editFactorClaims(null, true),
                    icon: const Icon(Icons.fact_check_outlined),
                    label: const Text(
                      'Faktor-Monat mit Ansprüchen und bezahlten Reisen',
                    ),
                  ),
                if (writable &&
                    pending == null &&
                    session.hasFeature(payrollFactorClaimsFeature))
                  FilledButton.icon(
                    onPressed: busy ? null : () => editFactorClaims(),
                    icon: const Icon(Icons.fact_check),
                    label: const Text(
                      'Faktor-Monat mit belegten Lohnansprüchen',
                    ),
                  ),
                if (writable &&
                    pending == null &&
                    session.hasFeature('payroll_factor_taxfree_travel'))
                  FilledButton.icon(
                    onPressed: busy ? null : () => editFactorTravel(),
                    icon: const Icon(Icons.travel_explore),
                    label: const Text(
                      'Faktor-Vollmonat mit bezahlter steuerfreier Reise',
                    ),
                  ),
                for (final fact in businessItems(
                  sources!['calculation_cases'],
                ).where((v) => v['details']['month'] == month))
                  ListTile(
                    title: Text(
                      'Abrechnungsfall $month · Fassung ${fact['revision']}',
                    ),
                    subtitle: Text(
                      fact['status'] == 'active' ? 'Aktiv' : 'Aufgehoben',
                    ),
                    onTap: busy ? null : () => act(() => inspect(fact)),
                  ),
                if (businessItems(sources!['calculation_cases'])
                    .where((v) => v['details']['month'] == month)
                    .isEmpty)
                  const BusinessEmpty(
                    'Noch kein bestätigter Gesamtfall',
                    'Wählen Sie die tatsächlichen Quellen und prüfen Sie den Fall vor dem Lohnabschluss.',
                  ),
              ],
            ],
          ),
  );
}

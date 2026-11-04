import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_entitlement_contract.dart';
export 'business_payroll_entitlement_contract.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;

Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Never _fail(String message, [int status = 0]) =>
    throw ApiException(status, message);
String _note(dynamic value, String label) {
  if (value is! String ||
      value.trim().isEmpty ||
      value.trim().length > 3000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(value))
    _fail('$label ausdrücklich belegen.', 400);
  return value.trim();
}

String _money(dynamic value) => value is int
    ? businessMoney(
        '${value ~/ 100}.${(value.abs() % 100).toString().padLeft(2, '0')}',
      )
    : 'Nicht ermittelt';
String _decimal(dynamic value) => value is int
    ? '${value ~/ 100}.${(value.abs() % 100).toString().padLeft(2, '0')}'
    : '';

bool payrollEntitlementsReadable(BusinessSession session) =>
    session.allowed &&
    session.projectId == null &&
    session.hasFeature('payroll_entitlements') &&
    session.hasModule('payroll_entitlements') &&
    session.can('personnel.read');

class PayrollEntitlementPlanView extends StatelessWidget {
  const PayrollEntitlementPlanView({
    super.key,
    required this.kind,
    required this.plan,
  });
  final String kind;
  final Map<String, dynamic> plan;
  Widget line(String name, String value) =>
      ListTile(dense: true, title: Text(name), subtitle: Text(value));
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      if (kind == 'sickness_history') ...[
        for (final entry in businessItems(
          plan['prevention_cases'] ?? [],
        ).indexed)
          ExpansionTile(
            title: Text('Zusammenhängender Verhinderungsfall ${entry.$1 + 1}'),
            children: [
              line(
                'Ursprünglicher AU-Beginn',
                businessDate(
                  entry.$2['original_au_from'] ?? entry.$2['from_date'],
                ),
              ),
              line(
                'Zählung in dieser Beschäftigung ab',
                businessDate(entry.$2['count_from']),
              ),
              line(
                'Anfangsrest',
                '${entry.$2['initial_remaining_days']} Kalendertage',
              ),
              line(
                'Gemeinsames Fristende',
                businessDate(entry.$2['statutory_deadline']),
              ),
              line(
                'Entgeltfortzahlung',
                '${entry.$2['entitlement_calendar_days']} Kalendertage',
              ),
            ],
          ),
        for (final p in businessItems(plan['preemployment_periods'] ?? []))
          line(
            'Belegter Zeitraum vor Beschäftigungsbeginn',
            '${businessDate(p['from_date'])} – ${businessDate(p['to_date'])}: kein Entgeltanspruch aus dieser Beschäftigung.',
          ),
        if (plan['phases'] is List)
          ExpansionTile(
            title: const Text('Geprüfte Phasen ohne doppelte Tageszählung'),
            children: [
              for (final p in businessItems(plan['phases']))
                line(
                  '${businessDate(p['from_date'])} – ${businessDate(p['to_date'])}',
                  'Vorzeitenfall ${businessItems(plan['episodes']).indexWhere((v) => v['episode_id'] == p['responsible_episode_id']) + 1}: ${p['first_day_remaining_regular_wage'] == true
                      ? 'Gewöhnlicher Restlohn des begonnenen Arbeitstags'
                      : p['entitled'] == true
                      ? 'Entgeltfortzahlung'
                      : p['waiting_period'] == true
                      ? 'Wartezeit'
                      : 'Kein Entgeltfortzahlungsanspruch'}',
                ),
            ],
          ),
      ],
      if (kind == 'sickness_history')
        for (final p in businessItems(plan['episodes']))
          ExpansionTile(
            title: Text(
              'Krankheitsfall ${businessDate(p['from_date'])} – ${businessDate(p['to_date'])}',
            ),
            children: [
              line('Zählung ab', businessDate(p['count_from'])),
              line('Wartezeit bis', businessDate(p['waiting_period_end'])),
              line(
                'Entgeltfortzahlung von',
                p['entitlement_from'] == null
                    ? 'Kein belegter Anspruch'
                    : businessDate(p['entitlement_from']),
              ),
              line(
                'Entgeltfortzahlung bis',
                p['entitlement_to'] == null
                    ? 'Kein belegter Anspruch'
                    : businessDate(p['entitlement_to']),
              ),
              line('Verbrauchte Vortage', '${p['prior_used_days']}'),
              line('Verbleibende Tage', '${p['remaining_days']}'),
              line(
                'Restlicher erster Arbeitstag',
                p['first_day_remaining_regular_wage'] == null
                    ? 'Nicht einschlägig'
                    : businessDate(p['first_day_remaining_regular_wage']),
              ),
            ],
          ),
      if (kind == 'regular_absence') ...[
        for (final p in businessItems(plan['days']))
          line(
            businessDate(p['date']),
            'Bezahlte Ausfallzeit: ${p['paid_absence_seconds']} Sekunden · tatsächliche Arbeit: ${p['actual_work_seconds']} Sekunden',
          ),
        line('Belegtes Ausfallentgelt', _money(plan['gross_minor'])),
      ],
      if (kind == 'vacation_reference') ...[
        line(
          'Referenzzeitraum',
          '${businessDate(plan['reference_from'])} – ${businessDate(plan['reference_to'])}',
        ),
        line(
          'Exaktes Tagesmittel',
          '${plan['workday_average']?['numerator']} / ${plan['workday_average']?['denominator']}',
        ),
        line(
          'Belegte Urlaubstage',
          (plan['vacation_days'] as List).map(businessDate).join(', '),
        ),
        line('Urlaubsentgelt', _money(plan['gross_minor'])),
        line(
          'Sachbezugsersatz',
          _money(plan['in_kind_cash_compensation_minor']),
        ),
        line('Fällig vor', businessDate(plan['due_before'])),
      ],
      if (kind == 'unpaid_continuation') ...[
        for (final p in businessItems(plan['intervals']))
          line(
            '${businessDate(p['from'])} – ${businessDate(p['to'])}',
            '${p['calendar_days']} Kalendertage · beitragspflichtige Beschäftigung besteht ${p['employment_for_contributions_continues'] == true ? 'fort' : 'nicht fort'}',
          ),
        for (final p in businessItems(plan['continuation_windows']))
          line(
            'Gesetzliche Monatsfrist bis',
            businessDate(p['statutory_deadline']),
          ),
      ],
      const Notice(
        'Dieser Nachweis bestätigt den ausgewiesenen Anspruchsbaustein. Lohnberechnung, Zahlung und Meldung bleiben gesonderte Vorgänge; tatsächliche Projektzeit bleibt unverändert.',
      ),
    ],
  );
}

class BusinessPayrollEntitlementsPage extends StatefulWidget {
  const BusinessPayrollEntitlementsPage({
    super.key,
    required this.session,
    required this.employee,
    required this.onOriginal,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final Future<void> Function(Map<String, dynamic>) onOriginal;
  @override
  State<BusinessPayrollEntitlementsPage> createState() =>
      _BusinessPayrollEntitlementsPageState();
}

class _BusinessPayrollEntitlementsPageState
    extends State<BusinessPayrollEntitlementsPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get commandKey => 'payroll-entitlements-$employeeId';
  Map<String, dynamic>? sources, selected, preview, previewBody, correction;
  List<Map<String, dynamic>> history = [];
  bool loading = false, busy = false, historical = false, suspended = false;
  String? error;
  Object? generation, activeAction;
  bool? approvalState;
  int epoch = 0;
  final privateDialogs = <DialogRoute<dynamic>>[];
  final pageScroll = ScrollController();
  bool get readable => !suspended && payrollEntitlementsReadable(session);
  bool get permitted =>
      readable && !session.readonly && session.can('personnel.approve');
  bool get writable =>
      permitted &&
      session.sectionEnabled('personnel') &&
      sources?['writes_enabled'] == true &&
      sources?['can_approve'] == true;
  Map<String, dynamic>? get pending =>
      session.pendingCommandValues(commandKey, path: '/payroll/entitlements');
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    session.addListener(changed);
    approvalState = permitted;
    load();
  }

  @override
  void didUpdateWidget(covariant BusinessPayrollEntitlementsPage oldWidget) {
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
    activeAction = null;
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
          : 'Der Anspruchsvorgang konnte nicht abgeschlossen werden.';
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
        value = payrollEntitlementSources(
          await session.read(
            '/payroll/entitlements/sources?employee_id=$employeeId',
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
        'Neue Anspruchsnachweise sind im pausierten Personalbereich gesperrt.',
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
    final record = payrollEntitlementRecord(fact, employeeId),
        page = await fresh();
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
    final result = await session.repeatPayrollEntitlementsCommand(employeeId);
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
        'Zuerst den unbestätigten ursprünglichen Anspruchsauftrag klären.',
        409,
      );
    final result = payrollEntitlementRecord(
      await session.command(
        commandKey,
        '/payroll/entitlements',
        body,
        validateResult: payrollEntitlementValidator(
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
    dynamic items,
    String Function(Map<String, dynamic>) label, {
    bool empty = true,
  }) => {
    if (empty) '': 'Bitte ausdrücklich auswählen',
    for (final item in businessItems(items)) '${item['id']}': label(item),
  };
  BusinessField files(
    Map<String, dynamic> page,
    String name,
    String label, [
    dynamic initial,
  ]) => BusinessField(
    name,
    label,
    type: BusinessInput.multiple,
    required: true,
    initial: initial,
    choices: choices(page['files'], (v) => '${v['filename']}', empty: false),
  );
  BusinessField yesNo(String name, String label, dynamic initial) =>
      BusinessField(
        name,
        label,
        type: BusinessInput.choice,
        required: true,
        initial: initial == true
            ? 'yes'
            : initial == false
            ? 'no'
            : '',
        choices: const {
          '': 'Bitte ausdrücklich wählen',
          'yes': 'Ja, belegt',
          'no': 'Nein, belegt',
        },
      );
  bool boolean(dynamic value, String label) {
    if (!['yes', 'no'].contains(value))
      _fail('$label ausdrücklich mit Ja oder Nein belegen.', 400);
    return value == 'yes';
  }

  Future<Map<String, dynamic>?> choose(
    String title,
    List<BusinessField> fields, {
    Map<String, dynamic> initial = const {},
  }) async {
    final opening = epoch;
    Map<String, dynamic>? result;
    await privateDialog<bool>(
      (_) => BusinessEditor(
        session: session,
        title: title,
        fields: fields,
        initial: initial,
        readPermission: 'personnel.read',
        writePermission: 'personnel.approve',
        readAllowed: () => readable && opening == epoch,
        saveLabel: 'Konkrete Anspruchsangaben belegen',
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
      final page = await fresh(write: true);
      if (!mounted || !readable || opening != epoch) return;
      final details = businessMap(previous?['details']),
          input = businessMap(details['input']);
      final fields = <BusinessField>[
        BusinessField(
          'employment_terms_id',
          'Belegte Beschäftigungsfassung',
          type: BusinessInput.choice,
          required: true,
          initial: details['employment_terms_ref']?['id'],
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
          ),
        ),
        BusinessField(
          'agreement_ids',
          'Alle einschlägigen Entgeltvereinbarungen',
          type: BusinessInput.multiple,
          required: true,
          initial: businessItems(details['agreement_refs'] ?? [])
              .map((v) => v['id'])
              .toList(),
          choices: choices(
            page['agreements'],
            (v) =>
                '${businessDate(v['effective_from'])} · ${_money(v['amount_minor'])} / ${v['pay_basis'] == 'hourly' ? 'Stunde' : 'Monat'} · Fassung ${v['revision']}',
            empty: false,
          ),
        ),
        BusinessField(
          'work_schedule_ids',
          'Gebundene datierte Arbeitspläne',
          type: BusinessInput.multiple,
          initial: businessItems(details['work_schedule_refs'] ?? [])
              .map((v) => v['id'])
              .toList(),
          choices: choices(
            businessItems(page['facts'])
                .where(
                  (v) =>
                      v['kind'] == 'work_schedule' && v['status'] == 'active',
                )
                .toList(),
            (v) => '${v['details']['month']} · Fassung ${v['revision']}',
            empty: false,
          ),
        ),
        BusinessField(
          'preparation_ids',
          'Gebundene abgeschlossene Monatsvorbereitungen',
          type: BusinessInput.multiple,
          initial: businessItems(details['preparation_refs'] ?? [])
              .map((v) => v['id'])
              .toList(),
          choices: choices(
            page['preparations'],
            (v) => '${v['month']} · Fassung ${v['revision']}',
            empty: false,
          ),
        ),
        files(
          page,
          'source_file_ids',
          'Geschützte Originale für diesen Anspruch',
          previous?['source_file_ids'],
        ),
        BusinessField(
          'verification_note',
          'Nachvollziehbarer Anspruchsprüfvermerk',
          required: true,
          initial: details['verification_note'],
        ),
        if (previous != null)
          const BusinessField(
            'correction_reason',
            'Belegter Korrekturgrund',
            required: true,
          ),
      ];
      if (kind == 'sickness_history')
        fields.addAll([
          BusinessField(
            'sickness_mode',
            'Belegte Form des Krankheitsverlaufs',
            type: BusinessInput.choice,
            required: true,
            initial: input['employment_commencement'] != null
                ? 'preemployment'
                : input['prevention_cases'] != null
                ? 'combined'
                : previous != null
                ? 'separate'
                : '',
            choices: const {
              '': 'Bitte ausdrücklich wählen',
              ...payrollSicknessModes,
            },
          ),
          BusinessField(
            'complete_from',
            'Belegte vollständige Vorzeiten ab',
            type: BusinessInput.date,
            required: true,
            initial: input['complete_from'],
          ),
          BusinessField(
            'complete_through',
            'Belegte vollständige Vorzeiten bis',
            type: BusinessInput.date,
            required: true,
            initial: input['complete_through'],
          ),
          BusinessField(
            'count',
            'Anzahl vollständig belegter Krankheitsfälle, auch bekannte 0',
            type: BusinessInput.integer,
            required: true,
            initial: (input['episodes'] as List?)?.length,
          ),
        ]);
      if (kind == 'regular_absence')
        fields.addAll([
          BusinessField(
            'absence_kind',
            'Belegte Art der regelmäßigen Ausfallvergütung',
            type: BusinessInput.choice,
            required: true,
            initial: input['kind'],
            choices: const {
              '': 'Bitte ausdrücklich wählen',
              ...payrollAbsenceKinds,
            },
          ),
          BusinessField(
            'sickness_history_id',
            'Geprüfter Krankheitsverlauf bei Krankheit',
            type: BusinessInput.choice,
            initial: details['sickness_history_ref']?['id'],
            choices: {
              ...choices(
                businessItems(page['entitlements'])
                    .where(
                      (v) =>
                          v['kind'] == 'sickness_history' &&
                          v['status'] == 'active',
                    )
                    .toList(),
                (v) =>
                    '${businessDate(v['effective_from'])} – ${businessDate(v['effective_to'])} · Fassung ${v['revision']}',
                empty: false,
              ),
            },
          ),
          BusinessField(
            'from',
            'Erster tatsächlich zu prüfender Ausfalltag',
            type: BusinessInput.date,
            required: true,
            initial: businessItems(input['days'] ?? []).firstOrNull?['date'],
          ),
          BusinessField(
            'to',
            'Letzter tatsächlich zu prüfender Ausfalltag',
            type: BusinessInput.date,
            required: true,
            initial: businessItems(input['days'] ?? []).lastOrNull?['date'],
          ),
        ]);
      if (kind == 'vacation_reference')
        fields.addAll([
          BusinessField(
            'vacation_from',
            'Erster tatsächlicher Urlaubstag',
            type: BusinessInput.date,
            required: true,
            initial: input['vacation_from'],
          ),
          BusinessField(
            'vacation_to',
            'Letzter tatsächlicher Urlaubstag',
            type: BusinessInput.date,
            required: true,
            initial: input['vacation_to'],
          ),
          BusinessField(
            'in_kind_daily',
            'Belegter täglicher Sachbezugsersatz (EUR), auch bekannte 0',
            type: BusinessInput.decimal,
            required: true,
            initial: _decimal(input['in_kind_daily_minor']),
          ),
        ]);
      if (kind == 'unpaid_continuation')
        fields.addAll([
          BusinessField(
            'from',
            'Tatsächlicher Beginn ohne Entgeltanspruch',
            type: BusinessInput.date,
            required: true,
            initial: input['from'],
          ),
          BusinessField(
            'to',
            'Tatsächliches Ende des zu prüfenden Zeitraums',
            type: BusinessInput.date,
            required: true,
            initial: input['to'],
          ),
          BusinessField(
            'count',
            'Anzahl belegter Ausnahmetatbestände, auch bekannte 0',
            type: BusinessInput.integer,
            required: true,
            initial: (input['exceptions'] as List?)?.length,
          ),
          const BusinessField(
            'employment_continues',
            'Das Beschäftigungsverhältnis besteht nach Beleg fort.',
            type: BusinessInput.toggle,
          ),
          const BusinessField(
            'no_wage_claim',
            'Für diesen Zeitraum besteht nach Beleg kein Entgeltanspruch.',
            type: BusinessInput.toggle,
          ),
          const BusinessField(
            'no_intervening_paid_days',
            'Es gibt keine dazwischenliegenden entgeltberechtigten Tage.',
            type: BusinessInput.toggle,
          ),
        ]);
      final values = await choose(
        '${previous == null ? 'Erfassen' : 'Korrigieren'}: ${payrollEntitlementKinds[kind]}',
        fields,
      );
      if (values == null || !mounted || !readable || opening != epoch) return;
      values['case_key'] = details['case_key'] ?? offlineId();
      await typed(page, kind, values, previous);
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> typed(
    Map<String, dynamic> page,
    String kind,
    Map<String, dynamic> values,
    Map<String, dynamic>? previous,
  ) async {
    final opening = epoch;
    final prior = businessMap(previous?['details']?['input']),
        outer = values['source_file_ids'];
    if (outer is! List || outer.isEmpty)
      _fail('Geschützte Anspruchsoriginale auswählen.', 400);
    final terms = businessItems(page['facts'])
        .where(
          (v) =>
              v['id'] == values['employment_terms_id'] &&
              v['kind'] == 'employment_terms' &&
              v['status'] == 'active',
        )
        .firstOrNull;
    if (terms == null)
      _fail('Die konkrete Beschäftigungsfassung auswählen.', 400);
    final agreements = businessItems(page['agreements'])
        .where((v) => (values['agreement_ids'] as List).contains(v['id']))
        .toList();
    if (agreements.isEmpty)
      _fail('Einschlägige Entgeltvereinbarungen auswählen.', 400);
    final fields = <BusinessField>[],
        originalPage = {
          ...page,
          'files': businessItems(page['files'])
              .where((v) => outer.contains(v['id']))
              .toList(),
        };
    BusinessField evidence(String name, String label, dynamic priorRefs) =>
        files(
          originalPage,
          name,
          label,
          businessItems(priorRefs ?? []).map((v) => v['id']).toList(),
        );
    List<Map<String, dynamic>> refs(String name, Map<String, dynamic> input) =>
        payrollEntitlementEvidence(page, input[name], outer);
    late Map<String, dynamic> Function(Map<String, dynamic>) assemble;
    final count = values['count'];
    if (['sickness_history', 'unpaid_continuation'].contains(kind) &&
        (count is! int || count < 0 || count > 2000))
      _fail('Eine tatsächliche Anzahl von 0 bis 2000 angeben.', 400);
    if (kind == 'sickness_history') {
      if (agreements.any(
        (v) => v['pay_basis'] != agreements.first['pay_basis'],
      ))
        _fail(
          'Wechselnde Entgeltbasen benötigen getrennte belegte Verhinderungsverläufe.',
          400,
        );
      payrollEntitlementDays(
        values['complete_from'],
        values['complete_through'],
      );
      final mode = values['sickness_mode'], phased = mode != 'separate';
      if (!payrollSicknessModes.containsKey(mode))
        _fail(
          'Die tatsächliche Form des Krankheitsverlaufs ausdrücklich wählen.',
          400,
        );
      final oldEpisodes = businessItems(prior['episodes'] ?? []),
          episodes = List.generate(
            count as int,
            (i) => {
              'id': i < oldEpisodes.length ? oldEpisodes[i]['id'] : offlineId(),
              'group': offlineId(),
              'case_id': offlineId(),
              'old': i < oldEpisodes.length
                  ? oldEpisodes[i]
                  : <String, dynamic>{},
            },
          );
      fields.add(
        evidence(
          'history_files',
          'Originale für die Vollständigkeit der Vorzeiten',
          prior['history_evidence_refs'],
        ),
      );
      final oldCases = businessItems(prior['prevention_cases'] ?? []);
      if (phased)
        fields.add(
          evidence(
            'prevention_files',
            'Originale für die zusammenhängenden Verhinderungsfälle und ihre Zuordnung',
            {
              for (final item in oldCases)
                for (final ref in businessItems(item['evidence_refs']))
                  ref['id']: ref,
            }.values.toList(),
          ),
        );
      if (mode == 'preemployment')
        fields.addAll([
          BusinessField(
            'contract_concluded_on',
            'Tatsächliches Datum des Vertragsabschlusses vor der Erkrankung',
            type: BusinessInput.date,
            required: true,
            initial: prior['employment_commencement']?['contract_concluded_on'],
          ),
          evidence(
            'commencement_files',
            'Vertragsoriginal für den vereinbarten Beschäftigungsbeginn',
            prior['employment_commencement']?['evidence_refs'],
          ),
        ]);
      for (var i = 0; i < episodes.length; i++) {
        final old = businessMap(episodes[i]['old']),
            p = 'episode_${i}_',
            groupIndex = oldEpisodes.indexWhere(
              (v) => v['continuation_group'] == old['continuation_group'],
            );
        final oldCase = oldCases
                .where((v) => (v['episode_ids'] as List).contains(old['id']))
                .firstOrNull,
            caseIndex = oldCase == null
                ? -1
                : episodes.indexWhere(
                    (v) => (oldCase['episode_ids'] as List).contains(v['id']),
                  );
        if (oldCase != null && caseIndex == i)
          episodes[i]['case_id'] = oldCase['id'];
        fields.addAll([
          BusinessField(
            '${p}from',
            'Vorzeitenfall ${i + 1}: Beginn',
            type: BusinessInput.date,
            required: true,
            initial: old['from'],
          ),
          BusinessField(
            '${p}to',
            'Vorzeitenfall ${i + 1}: Ende',
            type: BusinessInput.date,
            required: true,
            initial: old['to'],
          ),
          BusinessField(
            '${p}onset',
            'Vorzeitenfall ${i + 1}: tatsächlicher Beginn zur Arbeit',
            type: BusinessInput.choice,
            required: true,
            initial: old['onset'],
            choices: {
              '': 'Bitte ausdrücklich wählen',
              ...payrollOnsets,
              if (phased)
                'during_existing_au':
                    'Hinzugetreten während bestehender Arbeitsunfähigkeit',
              if (mode == 'preemployment')
                'before_employment':
                    'Nach Vertragsabschluss, vor Beschäftigungsbeginn',
            },
          ),
          BusinessField(
            '${p}first_scheduled_day',
            'Vorzeitenfall ${i + 1}: erster ausgefallener Solltag nur bei Stundenlohn-AU am freien Tag',
            type: BusinessInput.date,
            initial: old['first_scheduled_day'],
          ),
          BusinessField(
            '${p}group',
            'Vorzeitenfall ${i + 1}: belegter Fortsetzungszusammenhang',
            type: BusinessInput.choice,
            required: true,
            initial: old['continuation_group'] == null
                ? ''
                : groupIndex < i
                ? 'same:$groupIndex'
                : 'new',
            choices: {
              '': 'Bitte ausdrücklich wählen',
              'new': 'Eigenständiger Fortsetzungsfall',
              for (var j = 0; j < i; j++)
                'same:$j':
                    'Derselbe Fortsetzungsfall wie Vorzeitenfall ${j + 1}',
            },
          ),
          if (phased)
            BusinessField(
              '${p}case',
              'Vorzeitenfall ${i + 1}: belegter Verhinderungsfall',
              type: BusinessInput.choice,
              required: true,
              initial: oldCase == null
                  ? ''
                  : caseIndex < i
                  ? 'same:$caseIndex'
                  : 'new',
              choices: {
                '': 'Bitte ausdrücklich wählen',
                'new': 'Neuer Verhinderungsfall nach belegter Arbeitsfähigkeit',
                for (var j = 0; j < i; j++)
                  'same:$j':
                      'Hinzugetreten zum Verhinderungsfall von Vorzeitenfall ${j + 1}',
              },
            ),
          if (phased)
            yesNo(
              '${p}recovery_before',
              'Vorzeitenfall ${i + 1}: vorherige Arbeitsfähigkeit belegt (Nein bei fortbestehender AU)',
              null,
            ),
          if (!phased)
            BusinessField(
              '${p}recovery_before',
              'Vorzeitenfall ${i + 1}: Erholung vor dem neuen Verhinderungsfall ist belegt.',
              type: BusinessInput.toggle,
            ),
          BusinessField(
            '${p}unculpable',
            'Vorzeitenfall ${i + 1}: Unverschuldete Arbeitsverhinderung ist belegt.',
            type: BusinessInput.toggle,
          ),
          evidence(
            '${p}files',
            'Vorzeitenfall ${i + 1}: konkrete Originale',
            old['evidence_refs'],
          ),
        ]);
      }
      assemble = (input) {
        final rows = <Map<String, dynamic>>[];
        for (var i = 0; i < episodes.length; i++) {
          final item = episodes[i],
              old = businessMap(item['old']),
              p = 'episode_${i}_',
              choice = input['${p}group'];
          dynamic group;
          if (choice == 'new')
            group =
                oldEpisodes.indexWhere(
                      (v) =>
                          v['continuation_group'] == old['continuation_group'],
                    ) ==
                    i
                ? old['continuation_group']
                : item['group'];
          else if (choice is String &&
              RegExp(r'^same:\d+$').hasMatch(choice) &&
              int.parse(choice.substring(5)) < i)
            group = rows[int.parse(choice.substring(5))]['continuation_group'];
          else
            _fail('Den Fortsetzungszusammenhang ausdrücklich wählen.', 400);
          final recovery = phased
              ? boolean(
                  input['${p}recovery_before'],
                  'Belegte vorherige Arbeitsfähigkeit',
                )
              : input['${p}recovery_before'];
          if (recovery is! bool ||
              !phased && recovery != true ||
              input['${p}unculpable'] != true)
            _fail(
              'Ungeklärte Verhinderung oder Verschulden bleibt gesondert zu klären.',
              400,
            );
          rows.add({
            'id': item['id'],
            'from': payrollFactDate(input['${p}from']),
            'to': payrollFactDate(input['${p}to']),
            'onset': input['${p}onset'],
            'first_scheduled_day': payrollFactDate(
              input['${p}first_scheduled_day'],
              optional: true,
            ),
            'continuation_group': group,
            'recovery_before': recovery,
            'unculpable': true,
            'evidence_refs': refs('${p}files', input),
          });
        }
        return payrollSicknessStructure(
          {
            'employment_from': terms['details']['employment_from'],
            'employment_to': terms['details']['employment_to'],
            'pay_basis': agreements.first['pay_basis'],
            'complete_from': values['complete_from'],
            'complete_through': values['complete_through'],
            'history_evidence_refs': refs('history_files', input),
            'episodes': rows,
          },
          mode as String,
          caseChoices: [
            for (var i = 0; i < episodes.length; i++)
              '${input['episode_${i}_case'] ?? ''}',
          ],
          caseIds: [for (final item in episodes) item['case_id'] as String],
          evidenceRefs: phased ? refs('prevention_files', input) : [],
          commencement: mode == 'preemployment'
              ? {
                  'contract_concluded_on': payrollFactDate(
                    input['contract_concluded_on'],
                  ),
                  'evidence_refs': refs('commencement_files', input),
                }
              : null,
        );
      };
    } else if (kind == 'regular_absence') {
      final dates = payrollEntitlementDays(values['from'], values['to']);
      if (dates.length > 366)
        _fail('Höchstens 366 konkrete Ausfalltage je Anspruch wählen.', 400);
      final history = businessItems(page['entitlements'])
          .where(
            (v) =>
                v['id'] == values['sickness_history_id'] &&
                v['kind'] == 'sickness_history',
          )
          .firstOrNull;
      if (values['absence_kind'] != 'public_holiday' && history == null)
        _fail(
          'Für Krankheit den berechneten Vorzeiten-/Anspruchsnachweis auswählen.',
          400,
        );
      if (values['absence_kind'] == 'public_holiday' && history != null)
        _fail(
          'Ein eigenständiger Feiertagsfall verwendet keinen Krankheitsverlauf.',
          400,
        );
      final days = dates
          .map(
            (date) => {
              'date': date,
              ...payrollEntitlementDaySource(page, values, date),
            },
          )
          .toList();
      if (days.any(
        (v) =>
            v['agreement']['pay_basis'] != 'hourly' ||
            v['agreement']['amount_minor'] !=
                days.first['agreement']['amount_minor'],
      ))
        _fail(
          'Diese Ausfallvergütung benötigt einen unveränderten belegten regelmäßigen Stundenlohn.',
          400,
        );
      fields.add(
        evidence(
          'case_files',
          'Originale für die regelmäßige Ausfallvergütung',
          prior['evidence_refs'],
        ),
      );
      for (var i = 0; i < days.length; i++) {
        final day = days[i],
            p = 'day_${i}_',
            old =
                businessItems(prior['days'] ?? [])
                    .where((v) => v['date'] == day['date'])
                    .firstOrNull ??
                {};
        fields.addAll([
          yesNo(
            '${p}only',
            'Ausfalltag ${day['date']}: Abwesenheit ist alleiniger Ausfallgrund (Soll ${day['scheduled']} s, Ist ${day['worked']} s)',
            old['absence_is_only_cause'],
          ),
          if (values['absence_kind'] == 'public_holiday')
            yesNo(
              '${p}adjacent',
              'Feiertag ${day['date']}: Unentschuldigtes Fehlen unmittelbar davor oder danach',
              old['holiday_adjacent_unexcused'],
            ),
          evidence(
            '${p}files',
            'Ausfalltag ${day['date']}: konkrete Originale',
            old['evidence_refs'],
          ),
        ]);
      }
      assemble = (input) => {
        'kind': values['absence_kind'],
        'hourly_rate_minor': days.first['agreement']['amount_minor'],
        'evidence_refs': refs('case_files', input),
        'days': [
          for (var i = 0; i < days.length; i++)
            {
              'date': days[i]['date'],
              'scheduled_regular_seconds': days[i]['scheduled'],
              'worked_regular_seconds': days[i]['worked'],
              'entitled':
                  values['absence_kind'] == 'public_holiday' ||
                  businessItems(history?['plan']?['episodes'] ?? []).any(
                    (v) =>
                        values['absence_kind'] ==
                            'first_sickness_day_regular_wage'
                        ? v['first_day_remaining_regular_wage'] ==
                              days[i]['date']
                        : v['entitlement_from'] != null &&
                              (v['entitlement_from'] as String).compareTo(
                                    days[i]['date'],
                                  ) <=
                                  0 &&
                              (v['entitlement_to'] as String).compareTo(
                                    days[i]['date'],
                                  ) >=
                                  0,
                  ),
              'absence_is_only_cause': boolean(
                input['day_${i}_only'],
                'Alleiniger Ausfallgrund',
              ),
              'holiday_adjacent_unexcused':
                  values['absence_kind'] == 'public_holiday'
                  ? boolean(input['day_${i}_adjacent'], 'Feiertagsausschluss')
                  : null,
              'evidence_refs': refs('day_${i}_files', input),
            },
        ],
      };
    } else if (kind == 'vacation_reference') {
      final vacation = payrollEntitlementDays(
            values['vacation_from'],
            values['vacation_to'],
          ),
          first = DateTime.parse('${values['vacation_from']}T12:00:00Z');
      final reference = payrollEntitlementDays(
        first
            .subtract(const Duration(days: 91))
            .toIso8601String()
            .substring(0, 10),
        first
            .subtract(const Duration(days: 1))
            .toIso8601String()
            .substring(0, 10),
      );
      int scheduled(String date) {
        final rows = businessItems(page['facts'])
            .where(
              (v) =>
                  (values['work_schedule_ids'] as List).contains(v['id']) &&
                  v['kind'] == 'work_schedule',
            )
            .expand(
              (v) =>
                  businessItems(v['details']['days'])
                      .where((v) => v['date'] == date),
            )
            .toList();
        if (rows.length != 1)
          _fail(
            'Für den Referenztag $date fehlt eine eindeutige belegte Sollplanfassung.',
            400,
          );
        return rows.single['scheduled_seconds'];
      }

      final actual = vacation
          .map(
            (date) => {
              'date': date,
              ...payrollEntitlementDaySource(page, values, date),
            },
          )
          .where((v) => v['scheduled'] > 0)
          .toList();
      if (actual.isEmpty)
        _fail('Keine belegten Soll-Urlaubstage im gewählten Zeitraum.', 400);
      for (final date in reference) scheduled(date);
      fields.add(
        evidence(
          'case_files',
          'Originale für die gesamte Urlaubsreferenz',
          prior['evidence_refs'],
        ),
      );
      const amounts = {
        'base_earnings_minor': 'Belegter Grundverdienst',
        'overtime_earnings_minor': 'Darin enthaltene Überstundenvergütung',
        'protected_reduction_minor': 'Belegte geschützte Entgeltminderung',
        'permanent_raise_minor': 'Belegte dauerhafte Verdiensterhöhung',
      };
      for (var i = 0; i < reference.length; i++) {
        final date = reference[i],
            old =
                businessItems(prior['reference_days'] ?? [])
                    .where((v) => v['date'] == date)
                    .firstOrNull ??
                {};
        for (final entry in amounts.entries)
          fields.add(
            BusinessField(
              'reference_${i}_${entry.key}',
              '$date: ${entry.value} (EUR), auch bekannte 0',
              type: BusinessInput.decimal,
              required: true,
              initial: _decimal(old[entry.key]),
            ),
          );
        fields.add(
          evidence(
            'reference_${i}_files',
            '$date: konkrete Referenzoriginale',
            old['evidence_refs'],
          ),
        );
      }
      for (var i = 0; i < actual.length; i++)
        fields.add(
          evidence(
            'vacation_${i}_files',
            'Urlaubstag ${actual[i]['date']}: konkrete Originale',
            businessItems(prior['vacation_days'] ?? [])
                .where((v) => v['date'] == actual[i]['date'])
                .firstOrNull?['evidence_refs'],
          ),
        );
      assemble = (input) => {
        'vacation_from': values['vacation_from'],
        'vacation_to': values['vacation_to'],
        'in_kind_daily_minor': payrollEntitlementMoney(values['in_kind_daily']),
        'evidence_refs': refs('case_files', input),
        'reference_days': [
          for (var i = 0; i < reference.length; i++)
            {
              'date': reference[i],
              'contractual_workday': scheduled(reference[i]) > 0,
              for (final name in amounts.keys)
                name: payrollEntitlementMoney(input['reference_${i}_$name']),
              'evidence_refs': refs('reference_${i}_files', input),
            },
        ],
        'vacation_days': [
          for (var i = 0; i < actual.length; i++)
            {
              'date': actual[i]['date'],
              'scheduled_regular_seconds': actual[i]['scheduled'],
              'evidence_refs': refs('vacation_${i}_files', input),
            },
        ],
      };
    } else {
      payrollEntitlementDays(values['from'], values['to']);
      if (values['employment_continues'] != true ||
          values['no_wage_claim'] != true ||
          values['no_intervening_paid_days'] != true)
        _fail(
          'Fortbestehende Beschäftigung, fehlenden Entgeltanspruch und fehlende Zwischentage ausdrücklich belegen.',
          400,
        );
      fields.add(
        evidence(
          'case_files',
          'Originale für die unbezahlte Unterbrechung',
          prior['evidence_refs'],
        ),
      );
      final oldExceptions = businessItems(prior['exceptions'] ?? []);
      for (var i = 0; i < (count as int); i++) {
        final p = 'exception_${i}_',
            old = i < oldExceptions.length
                ? oldExceptions[i]
                : <String, dynamic>{};
        fields.addAll([
          BusinessField(
            '${p}kind',
            'Ausnahmetatbestand ${i + 1}: belegte Art',
            type: BusinessInput.choice,
            required: true,
            initial: old['kind'],
            choices: const {
              '': 'Bitte ausdrücklich wählen',
              ...payrollContinuationExceptions,
            },
          ),
          BusinessField(
            '${p}from',
            'Ausnahmetatbestand ${i + 1}: von',
            type: BusinessInput.date,
            required: true,
            initial: old['from'],
          ),
          BusinessField(
            '${p}to',
            'Ausnahmetatbestand ${i + 1}: bis',
            type: BusinessInput.date,
            required: true,
            initial: old['to'],
          ),
          BusinessField(
            '${p}scope',
            'Ausnahmetatbestand ${i + 1}: betrifft nach Beleg dieses Beschäftigungsverhältnis.',
            type: BusinessInput.toggle,
          ),
          evidence(
            '${p}files',
            'Ausnahmetatbestand ${i + 1}: konkrete Originale',
            old['evidence_refs'],
          ),
        ]);
      }
      assemble = (input) => {
        'from': values['from'],
        'to': values['to'],
        'employment_to': terms['details']['employment_to'],
        'employment_continues': true,
        'no_wage_claim': true,
        'intervening_paid_days': [],
        'evidence_refs': refs('case_files', input),
        'exceptions': [
          for (var i = 0; i < count; i++)
            {
              'kind': input['exception_${i}_kind'],
              'from': payrollFactDate(input['exception_${i}_from']),
              'to': payrollFactDate(input['exception_${i}_to']),
              'employment_scope': input['exception_${i}_scope'] == true
                  ? 'this_employment'
                  : _fail(
                      'Die Ausnahme ausdrücklich diesem Beschäftigungsverhältnis zuordnen.',
                      400,
                    ),
              'evidence_refs': refs('exception_${i}_files', input),
            },
        ],
      };
    }
    fields.add(
      const BusinessField(
        'confirmed',
        'Ich bestätige diese konkreten Anspruchsangaben und Originale.',
        type: BusinessInput.toggle,
      ),
    );
    final captured = session.generation;
    Map<String, dynamic>? nextBody, nextPreview;
    if (!mounted) return;
    await privateDialog<bool>(
      (_) => BusinessEditor(
        session: session,
        title: 'Konkrete Angaben: ${payrollEntitlementKinds[kind]}',
        fields: fields,
        readPermission: 'personnel.read',
        writePermission: 'personnel.approve',
        readAllowed: () => readable && opening == epoch,
        saveLabel: 'Anspruch unverbindlich prüfen',
        onSave: (input) async {
          if (input['confirmed'] != true)
            _fail(
              'Die konkreten Anspruchsangaben ausdrücklich bestätigen.',
              400,
            );
          await fresh(write: true);
          if (captured != session.generation || opening != epoch)
            _fail(
              'Der freigegebene Quellenstand wurde geändert. Den Vorgang neu öffnen.',
              409,
            );
          late Map<String, dynamic> body;
          try {
            body = payrollEntitlementInput(employeeId, page, kind, {
              ...values,
              'input': assemble(input),
            }, previous: previous);
          } on ApiException catch (e) {
            throw ApiException(400, e.message);
          }
          nextPreview = payrollEntitlementPreview(
            await session.api.call(
              session.path('/payroll/entitlements/preview'),
              payrollEntitlementPreviewInput(body),
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
        preview = nextPreview;
        previewBody = nextBody;
        correction = previous == null ? null : _copy(previous);
        selected = null;
        history = [];
      });
      showBeginning();
    }
  }

  Future<void> confirm() async {
    if (preview == null || previewBody == null || !writable || pending != null)
      return;
    final proof = _copy(preview!),
        body = _copy(previewBody!),
        prior = correction == null ? null : _copy(correction!),
        opening = epoch;
    final confirmed = await privateDialog<bool>(
      (context) => AlertDialog(
        title: const Text('Geprüften Anspruchsbaustein festhalten'),
        content: const Text(
          'Ich bestätige genau diesen geprüften Anspruchsbaustein und seine Originale.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Anspruchsbaustein festhalten'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted || !readable || opening != epoch) return;
    await act(() => save(body, previous: prior, proof: proof));
  }

  Future<void> cancel(Map<String, dynamic> fact) async {
    if (pending != null) return;
    final opening = epoch;
    try {
      await fresh(write: true);
      if (!mounted || !readable || opening != epoch) return;
      await privateDialog<bool>(
        (_) => BusinessEditor(
          session: session,
          title: 'Fälschlichen Anspruch aufheben',
          fields: const [
            BusinessField(
              'correction_reason',
              'Belegter Aufhebungsgrund',
              required: true,
            ),
            BusinessField(
              'confirmed',
              'Ich bestätige die Aufhebung; frühere Abrechnungen bleiben unverändert.',
              type: BusinessInput.toggle,
            ),
          ],
          readPermission: 'personnel.read',
          writePermission: 'personnel.approve',
          readAllowed: () => readable && opening == epoch,
          pendingKey: commandKey,
          saveLabel: 'Anspruch belegt aufheben',
          onSave: (values) async {
            if (pending != null) {
              await session.repeatPayrollEntitlementsCommand(employeeId);
              return;
            }
            if (values['confirmed'] != true)
              _fail('Die Aufhebung ausdrücklich bestätigen.', 400);
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
              'correction_reason': _note(
                values['correction_reason'],
                'Aufhebungsgrund',
              ),
              'confirmed': true,
            }, previous: fact);
          },
        ),
      );
      if (mounted && readable && opening == epoch) await load();
    } catch (e) {
      if (mounted && readable && opening == epoch) failed(e);
    }
  }

  Future<void> showHistory(Map<String, dynamic> fact) => act(() async {
    await fresh();
    final captured = epoch,
        page = businessMap(
          await session.read('/payroll/entitlements/${fact['id']}/history'),
        ),
        items = businessItems(page['items']);
    if (page['employee_id'] != employeeId ||
        items.indexed.any(
          (entry) =>
              payrollEntitlementRecord(
                    entry.$2,
                    employeeId,
                    kind: fact['kind'],
                  )['id'] !=
                  fact['id'] ||
              entry.$2['revision'] != entry.$1 + 1,
        ))
      _fail('Die Anspruchshistorie gehört nicht zum gewählten Nachweis.');
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
            '${payrollEntitlementKinds[value['kind']]} · Fassung ${value['revision']}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text(
            value['status'] == 'void'
                ? 'Anspruch aufgehoben; Historie bleibt erhalten.'
                : 'Aktiver belegter Anspruch',
          ),
          Text('${value['details']['verification_note']}'),
          if ('${value['correction_reason'] ?? ''}'.isNotEmpty)
            Text('Korrekturgrund: ${value['correction_reason']}'),
          PayrollEntitlementPlanView(
            kind: value['kind'],
            plan: businessMap(value['plan']),
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
              child: const Text('Anspruchshistorie öffnen'),
            ),
          if (!historical &&
              value['status'] == 'active' &&
              writable &&
              pending == null)
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                OutlinedButton(
                  onPressed: busy ? null : () => edit(value['kind'], value),
                  child: const Text('Anspruch korrigieren'),
                ),
                OutlinedButton(
                  onPressed: busy ? null : () => cancel(value),
                  child: const Text('Fälschlichen Anspruch aufheben'),
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
      title: Text('Private Anspruchsnachweise · ${widget.employee['name']}'),
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
              'Anspruchsnachweise nicht freigegeben',
              'Diese privaten Nachweise benötigen aktuelle globale Personal-Leserechte.',
            ),
          )
        : ListView(
            controller: pageScroll,
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Private Nachweise zu Krankheitsvorzeiten, regelmäßiger Ausfallvergütung, Urlaubsentgelt und unbezahlten Unterbrechungen.',
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
                        const Text('Anspruchsbestätigung offen'),
                        const Notice(
                          'Der Auftrag kann bereits gespeichert sein. Die Wiederholung verwendet dieselben Werte und dieselbe Vorgangskennung.',
                        ),
                        if (permitted)
                          FilledButton(
                            onPressed: busy ? null : repeat,
                            child: const Text(
                              'Ursprünglichen Anspruchsauftrag erneut senden',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              if (preview != null) ...[
                Text(
                  'Anspruchsbaustein prüfen',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                PayrollEntitlementPlanView(
                  kind: preview!['kind'],
                  plan: businessMap(preview!['plan']),
                ),
                if (preview!['can_confirm'] == true &&
                    writable &&
                    pending == null)
                  FilledButton(
                    onPressed: busy ? null : confirm,
                    child: const Text('Geprüften Anspruchsbaustein festhalten'),
                  ),
              ],
              if (selected != null) recordView(selected!),
              for (final old in history)
                ListTile(
                  title: Text(
                    'Historische Anspruchsfassung ${old['revision']}',
                  ),
                  subtitle: Text('${old['correction_reason']}'),
                  onTap: busy ? null : () => act(() => inspect(old, old: true)),
                ),
              for (final kind in payrollEntitlementKinds.entries)
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
                          sources?['entitlements'] ?? [],
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
                  'Das Personalmodul ist pausiert. Historische Nachweise und unveränderte bereits angenommene Aufträge bleiben mit frischen Rechten zugänglich.',
                ),
            ],
          ),
  );
}

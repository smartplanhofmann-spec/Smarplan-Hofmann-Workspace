import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_payroll_facts.dart';
import 'business_payroll_multiple_case_contract.dart';
export 'business_payroll_multiple_case_contract.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;
import 'business_payroll_oneoff_cases.dart' show PayrollOneoffCasePlanView;

Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
Never _fail(String message, [int status = 400]) =>
    throw ApiException(status, message);
String _money(dynamic value) => value is int
    ? businessMoney(
        '${value ~/ 100}.${(value.abs() % 100).toString().padLeft(2, '0')}',
      )
    : 'Nicht berechenbar';
bool payrollMultipleCasesReadable(BusinessSession session) =>
    session.allowed &&
    session.projectId == null &&
    session.hasFeature('payroll_multiple_cases') &&
    session.hasModule('payroll_multiple_cases') &&
    session.can('personnel.read');

class PayrollMultipleCasePlanView extends StatelessWidget {
  const PayrollMultipleCasePlanView({super.key, required this.plan});
  final Map<String, dynamic> plan;
  Widget line(String title, String value) =>
      ListTile(dense: true, title: Text(title), subtitle: Text(value));
  @override
  Widget build(BuildContext context) {
    final detail = businessMap(plan['multiple_one_off_details']);
    final single = detail['single_original_calculation'];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        line('Lohnmonat', '${plan['month']}'),
        line(
          'Laufendes Originalbrutto',
          _money(plan['running_calculation']?['gross_minor']),
        ),
        line(
          'Geplante Bruttozuflüsse der Monatsgruppe',
          _money(detail['amount_minor']),
        ),
        for (final e in businessItems(detail['receipt_events']))
          line(
            'Geplanter Zuflusstag ${businessDate(e['receipt_date'])}',
            _money(e['gross_minor']),
          ),
        for (final c in businessItems(detail['components']))
          line(
            'Ursprünglicher Anspruch',
            'Geplant: ${_money(c['planned_minor'])} · Verbleibend: ${_money(c['remaining_claim_minor'])}',
          ),
        if (single is Map)
          PayrollOneoffCasePlanView(plan: businessMap(single))
        else ...[
          line('Berechnete Auszahlung', _money(plan['payout_minor'])),
          for (final b in businessItems(plan['blockers']))
            Notice('${b['message'] ?? b['reason'] ?? b['code']}', error: true),
          const Notice(
            'Mehrere Ansprüche oder Teilzuflüsse bleiben bis zur geprüften Steuer- und Beitragszuordnung als Plan gesperrt. Eine gemeinsame SV-Basis ersetzt keine geprüften Einzelnetti.',
          ),
        ],
        const Notice(
          'Die Monatsgruppe erzeugt keine Zahlung. Tatsächliche Überweisungen und deren getrennte Zuordnungen werden aus ihren Originalen belegt.',
        ),
      ],
    );
  }
}

class BusinessPayrollMultipleCasesPage extends StatefulWidget {
  const BusinessPayrollMultipleCasesPage({
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
  State<BusinessPayrollMultipleCasesPage> createState() =>
      _BusinessPayrollMultipleCasesPageState();
}

class _BusinessPayrollMultipleCasesPageState
    extends State<BusinessPayrollMultipleCasesPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get commandKey => 'payroll-multiple-$employeeId';
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
  bool get readable => !suspended && payrollMultipleCasesReadable(session);
  bool get permitted =>
      readable && !session.readonly && session.can('personnel.approve');
  bool get writable =>
      permitted &&
      session.sectionEnabled('personnel') &&
      sources?['writes_enabled'] == true &&
      sources?['can_approve'] == true;
  Map<String, dynamic>? get pending => session.pendingCommandValues(
    commandKey,
    path: '/payroll/multiple-one-off-cases',
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
  void didUpdateWidget(covariant BusinessPayrollMultipleCasesPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.employee['id'] != employeeId ||
        oldWidget.initialMonth != widget.initialMonth) {
      oldWidget.session.removeListener(changed);
      session.addListener(changed);
      epoch++;
      dismissPrivateDialogs(afterBuild: true);
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
    // A retained root Navigator can outlive this page.
    dismissPrivateDialogs(afterBuild: true);
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

  void dismissPrivateDialogs({bool afterBuild = false}) {
    final routes = privateDialogs.toList().reversed.toList();
    privateDialogs.clear();
    void remove() {
      for (final route in routes) {
        if (route.isActive) route.navigator?.removeRoute(route);
      }
    }

    // didUpdateWidget/dispose run while the Navigator may be building. The
    // captured routes need no later access to this page's disposed context.
    if (afterBuild && routes.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) => remove());
    } else {
      remove();
    }
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
          : 'Der Monatsgruppenvorgang konnte nicht abgeschlossen werden.';
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
      _fail('Monatsgruppenmonat im Jahr 2026 wählen.', 400);
    final captured = session.generation,
        value = payrollMultipleCaseSources(
          await session.read(
            '/payroll/multiple-one-off-cases/sources?employee_id=$employeeId&month=$wanted',
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
        'Neue Monatsgruppen sind im pausierten Personalbereich gesperrt.',
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
    final record = payrollMultipleCaseRecord(fact, employeeId),
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
    final result = await session.repeatPayrollMultipleCaseCommand(employeeId);
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
        'Zuerst den unbestätigten ursprünglichen Monatsgruppenauftrag klären.',
        409,
      );
    final result = payrollMultipleCaseRecord(
      await session.command(
        commandKey,
        '/payroll/multiple-one-off-cases',
        body,
        validateResult: payrollMultipleCaseValidator(
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
    String saveLabel = 'Monatsgruppe unverbindlich prüfen',
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
        title: const Text('Monatsgruppenmonat wählen'),
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
        _fail('Monatsgruppenmonat im Jahr 2026 wählen.');
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
      List<int> counts;
      if (previous != null) {
        counts = [
          for (final p in businessItems(d['components']))
            (p['planned_receipts'] as List).length,
        ];
      } else {
        final layout = await choose('Umfang der Monatsgruppe auswählen', const [
          BusinessField(
            'count',
            'Anzahl ursprünglicher Ansprüche',
            type: BusinessInput.integer,
            required: true,
            initial: 1,
          ),
        ]);
        if (layout == null || !mounted || !readable || opening != epoch) return;
        final count = layout['count'];
        if (count is! int || count < 1 || count > 20)
          _fail('Ein bis zwanzig ursprüngliche Ansprüche wählen.');
        final events = await choose('Zuflussereignisse je Anspruch auswählen', [
          for (var i = 0; i < count; i++)
            BusinessField(
              'count_$i',
              'Geplante Zuflüsse für Anspruch ${i + 1}',
              type: BusinessInput.integer,
              required: true,
              initial: 1,
            ),
        ]);
        if (events == null || !mounted || !readable || opening != epoch) return;
        counts = [
          for (var i = 0; i < count; i++)
            events['count_$i'] is int ? events['count_$i'] as int : 0,
        ];
        if (counts.any((n) => n < 1 || n > 20) ||
            counts.fold<int>(0, (a, b) => a + b) > 100)
          _fail(
            'Je Anspruch ein bis zwanzig, insgesamt höchstens hundert Ereignisse wählen.',
          );
      }
      final files = {
            for (final f in businessItems(page['files']))
              '${f['id']}': '${f['filename']}',
          },
          eventKeys = <List<String>>[];
      final fields = <BusinessField>[
        source(
          'running_calculation_case_id',
          'Unveränderter laufender Gesamtfall dieses Monats',
          businessItems(page['calculation_cases'])
              .where(
                (v) =>
                    v['status'] == 'active' && v['details']['month'] == wanted,
              )
              .toList(),
          initial: d['running_calculation_case_ref'],
        ),
        source(
          'current_annual_basis_id',
          'Vollständige Jahresbasis 2026',
          annual('annual_basis', year: 2026),
          initial: d['current_annual_basis_ref'],
        ),
        source(
          'previous_annual_basis_id',
          'Belegtes Vorjahr für eine mögliche Märzklausel',
          annual('annual_basis', year: 2025),
          initial: d['previous_annual_basis_ref'],
          required: false,
        ),
      ];
      final parts = businessItems(d['components'] ?? []);
      for (var i = 0; i < counts.length; i++) {
        final part = i < parts.length ? parts[i] : <String, dynamic>{},
            receipts = businessItems(part['planned_receipts'] ?? []),
            keys = <String>[];
        fields.add(
          source(
            'earning_$i',
            'Ursprünglicher Anspruch ${i + 1}',
            annual('one_off_earning'),
            initial: part['earning_ref'],
          ),
        );
        for (var j = 0; j < counts[i]; j++) {
          final receipt = j < receipts.length
                  ? receipts[j]
                  : <String, dynamic>{},
              event = receipt['event_key'] as String? ?? offlineId(),
              label = 'Anspruch ${i + 1} · Zufluss ${j + 1}';
          keys.add(event);
          final forecasts = businessItems(d['annual_tax_forecasts'] ?? [])
              .where((f) => f['event_key'] == event);
          fields.addAll([
            BusinessField(
              'date_${i}_$j',
              '$label · tatsächlicher Zuflusstag',
              type: BusinessInput.date,
              required: true,
              initial: receipt['receipt_date'],
            ),
            BusinessField(
              'gross_${i}_$j',
              '$label · belegtes Brutto (€)',
              required: true,
              initial: receipt['gross_minor'] is int
                  ? ((receipt['gross_minor'] as int) / 100).toStringAsFixed(2)
                  : null,
            ),
            BusinessField(
              'files_${i}_$j',
              '$label · konkrete Originale',
              type: BusinessInput.multiple,
              required: true,
              initial: [
                for (final r in businessItems(receipt['document_refs'] ?? []))
                  r['id'],
              ],
              choices: files,
            ),
            source(
              'forecast_${i}_$j',
              '$label · Steuerprognose des ursprünglichen Anspruchs',
              annual('annual_tax_forecast'),
              initial: forecasts.isEmpty
                  ? null
                  : forecasts.single['annual_tax_forecast_ref'],
              required: false,
            ),
          ]);
        }
        eventKeys.add(keys);
      }
      fields.addAll([
        BusinessField(
          'source_file_ids',
          'Alle geschützten Originale der Monatsgruppe',
          type: BusinessInput.multiple,
          required: true,
          initial: previous?['source_file_ids'],
          choices: files,
        ),
        BusinessField(
          'completeness_file_id',
          'Originalnachweis der vollständigen Monatsgruppe',
          type: BusinessInput.choice,
          required: true,
          initial: d['completeness']?['evidence_ref']?['id'],
          choices: {'': 'Original ausdrücklich auswählen', ...files},
        ),
        const BusinessField(
          'month_events_complete',
          'Ich habe sämtliche Ansprüche und Bruttozuflüsse dieses Monats vollständig anhand der Originale geprüft.',
          type: BusinessInput.toggle,
        ),
        BusinessField(
          'verification_note',
          'Nachvollziehbarer Monatsgruppen-Prüfvermerk',
          required: true,
          initial: d['verification_note'],
        ),
        if (previous != null)
          const BusinessField(
            'correction_reason',
            'Belegter Korrekturgrund',
            required: true,
          ),
      ]);
      final values = await choose(
        previous == null
            ? 'Monatsgruppe aus Originalen erfassen'
            : 'Monatsgruppe berichtigen',
        fields,
      );
      if (values == null || !mounted || !readable || opening != epoch) return;
      if (values['month_events_complete'] != true)
        _fail('Die konkrete Monatsgruppenzuordnung ausdrücklich bestätigen.');
      await act(() async {
        await fresh(write: true, forMonth: wanted);
        if (opening != epoch) return;
        final forecasts = <Map<String, dynamic>>[],
            components = <Map<String, dynamic>>[];
        for (var i = 0; i < counts.length; i++) {
          final receipts = <Map<String, dynamic>>[];
          for (var j = 0; j < counts[i]; j++) {
            final event = eventKeys[i][j],
                forecast = values['forecast_${i}_$j'];
            if (forecast != null && forecast != '')
              forecasts.add({'event_key': event, 'forecast_id': forecast});
            receipts.add({
              'event_key': event,
              'receipt_date': values['date_${i}_$j'],
              'gross_minor': payrollMultipleMoney(values['gross_${i}_$j']),
              'document_ids': values['files_${i}_$j'],
            });
          }
          components.add({
            'earning_id': values['earning_$i'],
            'receipts': receipts,
          });
        }
        final body = payrollMultipleCaseInput(employeeId, page, {
          ...values,
          'month': wanted,
          'components': components,
          'annual_tax_forecasts': forecasts,
        }, previous: previous);
        final checked = payrollMultipleCasePreview(
          await session.api.call(
            session.path('/payroll/multiple-one-off-cases/preview'),
            payrollMultipleCasePreviewInput(body),
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
        title: const Text('Geprüfte Monatsgruppe festhalten'),
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
            child: const Text('Monatsgruppe festhalten'),
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
      final reason = await choose('Fälschliche Monatsgruppe aufheben', [
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
      ], saveLabel: 'Monatsgruppe belegt aufheben');
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
          'kind': 'multiple_one_off_case',
          'rule_version': payrollMultipleRule,
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
          await session.read(
            '/payroll/multiple-one-off-cases/${fact['id']}/history',
          ),
        ),
        items = businessItems(page['items']);
    if (items.indexed.any(
      (entry) =>
          payrollMultipleCaseRecord(entry.$2, employeeId)['id'] != fact['id'] ||
          entry.$2['revision'] != entry.$1 + 1,
    ))
      _fail(
        'Die Monatsgruppenhistorie gehört nicht zur ursprünglichen Fassung.',
      );
    if (mounted && readable && opening == epoch)
      setState(() => history = items);
  });
  Future<void> calculate(Map<String, dynamic> fact) => act(() async {
    final opening = epoch,
        page = await fresh(write: true, forMonth: fact['details']['month']);
    final current = businessItems(page['multiple_one_off_cases'])
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
        'Die aktuelle berechenbare Monatsgruppenfassung erneut öffnen.',
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
            'Monatsgruppe ${value['details']['month']} · Fassung ${value['revision']}',
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
          PayrollMultipleCasePlanView(plan: businessMap(value['plan'])),
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
              child: const Text('Monatsgruppenhistorie öffnen'),
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
                    child: const Text('Lohn mit dieser Monatsgruppe berechnen'),
                  ),
                OutlinedButton(
                  onPressed: busy ? null : () => edit(value),
                  child: const Text('Monatsgruppe berichtigen'),
                ),
                OutlinedButton(
                  onPressed: busy ? null : () => cancel(value),
                  child: const Text('Fälschliche Monatsgruppe aufheben'),
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
      title: Text('Monatsgruppen · ${widget.employee['name']}'),
      actions: [
        IconButton(
          tooltip: 'Rechte und Monatsgruppenquellen aktualisieren',
          onPressed: busy || loading ? null : load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !readable
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: BusinessEmpty(
              'Monatsgruppen nicht freigegeben',
              'Diese privaten Nachweise benötigen aktuelle globale Personal-Leserechte.',
            ),
          )
        : ListView(
            controller: pageScroll,
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Die vollständige Monatsgruppe bindet ursprüngliche Ansprüche, ihre einzelnen Bruttozuflüsse und Jahresquellen. Tatsächliche Nettozahlungen bleiben eigenständige Nachweise.',
              ),
              Text('Gewählter Lohnmonat: $month'),
              OutlinedButton(
                onPressed: busy || pending != null ? null : chooseMonth,
                child: const Text('Monatsgruppenmonat wählen'),
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
                        const Text('Monatsgruppenbestätigung offen'),
                        const Notice(
                          'Der Auftrag kann bereits angenommen sein. Die Wiederholung erhält dieselben Angaben und dieselbe Vorgangskennung.',
                        ),
                        if (permitted)
                          FilledButton(
                            onPressed: busy ? null : repeat,
                            child: const Text(
                              'Ursprünglichen Monatsgruppenauftrag erneut senden',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              if (preview != null) ...[
                Text(
                  'Monatsgruppe prüfen',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                PayrollMultipleCasePlanView(
                  plan: businessMap(preview!['plan']),
                ),
                if (preview!['can_confirm'] == true &&
                    writable &&
                    pending == null)
                  FilledButton(
                    onPressed: busy ? null : confirm,
                    child: const Text('Geprüfte Monatsgruppe festhalten'),
                  ),
              ],
              if (selected != null) recordView(selected!),
              for (final fact in history)
                ListTile(
                  title: Text(
                    'Historische Monatsgruppenfassung ${fact['revision']}',
                  ),
                  subtitle: Text('${fact['correction_reason']}'),
                  onTap: busy
                      ? null
                      : () => act(() => inspect(fact, old: true)),
                ),
              const Text('Gespeicherte Monatsgruppen'),
              for (final fact in businessItems(
                sources?['multiple_one_off_cases'] ?? [],
              ).where((v) => v['details']['month'] == month))
                ListTile(
                  title: Text(
                    'Monatsgruppe ${fact['details']['month']} · Fassung ${fact['revision']}',
                  ),
                  subtitle: Text(
                    fact['status'] == 'void' ? 'Aufgehoben' : 'Aktiv',
                  ),
                  onTap: busy ? null : () => act(() => inspect(fact)),
                ),
              if (writable && pending == null)
                FilledButton(
                  onPressed: busy ? null : () => edit(),
                  child: const Text('Monatsgruppe erfassen'),
                ),
              if (sources?['writes_enabled'] == false)
                const Notice(
                  'Das Personalmodul ist pausiert. Originalfassungen und unveränderte bereits angenommene Aufträge bleiben mit aktuellen Rechten zugänglich.',
                ),
            ],
          ),
  );
}

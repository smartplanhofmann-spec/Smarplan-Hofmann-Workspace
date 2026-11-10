import 'package:flutter/material.dart';

import 'api.dart';
import 'business_payroll_rv_contract.dart';
export 'business_payroll_rv_contract.dart';
import 'business_session.dart';
import 'business_widgets.dart';

bool payrollRvReadable(BusinessSession session) =>
    session.allowed &&
    session.projectId == null &&
    session.hasFeature('payroll_rv_lifecycle') &&
    session.hasModule('payroll_rv_lifecycle') &&
    session.can('personnel.read');

class BusinessPayrollRvPage extends StatefulWidget {
  const BusinessPayrollRvPage({
    super.key,
    required this.session,
    required this.employee,
    required this.onOriginal,
  });
  final BusinessSession session;
  final Map<String, dynamic> employee;
  final Future<void> Function(Map<String, dynamic>) onOriginal;
  @override
  State<BusinessPayrollRvPage> createState() => _BusinessPayrollRvPageState();
}

class _BusinessPayrollRvPageState extends State<BusinessPayrollRvPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  String get employeeId => widget.employee['id'];
  String get commandKey => 'payroll-rv-lifecycle-$employeeId';
  Map<String, dynamic>? sources, selected, proof, body, previous;
  String? error;
  bool busy = false, accepted = false;
  int epoch = 0;
  Object? generation;
  BuildContext? editor;
  bool get readable => payrollRvReadable(session);
  bool get permitted =>
      readable && !session.readonly && session.can('personnel.approve');
  bool get writable =>
      permitted &&
      session.sectionEnabled('personnel') &&
      sources?['can_approve'] == true &&
      sources?['writes_enabled'] == true;
  bool get pending => session.pending(commandKey);
  @override
  void initState() {
    super.initState();
    generation = session.generation;
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
  void didUpdateWidget(covariant BusinessPayrollRvPage old) {
    super.didUpdateWidget(old);
    if (!identical(old.session, session) || old.employee['id'] != employeeId) {
      old.session.removeListener(changed);
      session.addListener(changed);
      epoch++;
      clear();
      generation = session.generation;
      load();
    }
  }

  void clear() {
    final privateEditor = editor;
    editor = null;
    sources = selected = proof = body = previous = null;
    accepted = false;
    busy = false;
    if (privateEditor != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (privateEditor.mounted &&
            ModalRoute.of(privateEditor)?.isCurrent == true)
          Navigator.of(privateEditor).pop();
      });
    }
  }

  void changed() {
    if (mounted &&
        (!readable ||
            (body != null || editor != null) && !permitted ||
            generation != session.generation)) {
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

  Never fail(String message, [int status = 400]) {
    if (mounted && [401, 403, 404].contains(status)) {
      epoch++;
      setState(clear);
    }
    throw ApiException(status, message);
  }

  Future<Map<String, dynamic>> fresh({
    bool write = false,
    bool replay = false,
  }) async {
    final captured = epoch;
    await session.load();
    if (!mounted ||
        !readable ||
        captured != epoch ||
        session.error != null ||
        write && !permitted)
      fail('Die aktuelle private Personalfreigabe fehlt.', 403);
    final stamp = session.generation,
        page = payrollRvSources(
          await session.read('$payrollRvPath/sources?employee_id=$employeeId'),
          employeeId,
        );
    if (!mounted ||
        !readable ||
        captured != epoch ||
        stamp != session.generation ||
        write && (!permitted || page['can_approve'] != true))
      fail(
        'Die private RV-Ansicht oder Mitarbeiterfreigabe wurde geändert.',
        403,
      );
    if (write &&
        !replay &&
        (!session.sectionEnabled('personnel') ||
            page['writes_enabled'] != true))
      fail('Der Personalbereich ist für neue RV-Nachweise pausiert.', 423);
    return page;
  }

  Future<void> operate(Future<void> Function() action) async {
    if (busy) return;
    final captured = epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } catch (e) {
      if (mounted && captured == epoch)
        setState(() {
          error = e is ApiException
              ? e.message
              : e is FormatException
              ? '${e.message}'
              : 'Der RV-Prüfstand konnte nicht abgeschlossen werden.';
          if (e is ApiException && [401, 403, 404].contains(e.status)) clear();
        });
    } finally {
      if (mounted && captured == epoch) setState(() => busy = false);
    }
  }

  Future<void> load() async {
    await operate(() async {
      final captured = epoch, page = await fresh();
      if (mounted && captured == epoch)
        setState(() {
          sources = page;
          selected = businessItems(page['history']).lastOrNull;
        });
    });
  }

  Future<void> repeat() async {
    await operate(() async {
      final captured = epoch;
      await fresh(write: true, replay: true);
      final result = payrollRvRecord(
        await session.repeatPayrollRvCommand(employeeId),
        employeeId,
      );
      final page = await fresh();
      if (mounted && captured == epoch)
        setState(() {
          selected = result;
          sources = page;
          proof = body = previous = null;
          accepted = false;
        });
    });
  }

  Future<void> confirm() async {
    if (!accepted || body == null || proof == null) return;
    await operate(() async {
      final captured = epoch, b = body!, p = proof!;
      await fresh(write: true);
      if (pending)
        fail('Zuerst die unveränderte ursprüngliche Anfrage klären.', 409);
      final record = payrollRvRecord(
        await session.command(
          commandKey,
          payrollRvPath,
          b,
          validateResult: payrollRvValidator(b, p, previous: previous),
        ),
        employeeId,
      );
      final page = await fresh();
      if (mounted && captured == epoch)
        setState(() {
          selected = record;
          sources = page;
          proof = body = previous = null;
          accepted = false;
        });
    });
  }

  Future<void> edit() async {
    final captured = epoch;
    Map<String, dynamic>? page;
    await operate(() async {
      page = await fresh(write: true);
    });
    if (!mounted || captured != epoch || page == null || pending) return;
    final s = page!,
        prior = businessItems(s['history']).lastOrNull,
        a = businessMap(prior?['details']?['assessment']),
        r = businessMap(a['revocation']),
        x = businessMap(a['established_exemption']);
    final fileChoices = {
      for (final f in businessItems(s['files']))
        '${f['id']}': '${f['filename']}',
    };
    BusinessField choice(
      String name,
      String label, {
      dynamic initial,
      Map<String, String>? choices,
      bool required = false,
    }) => BusinessField(
      name,
      label,
      type: BusinessInput.choice,
      choices: choices ?? fileChoices,
      initial: initial,
      required: required,
    );
    BusinessField date(
      String name,
      String label,
      dynamic value, {
      bool required = false,
    }) => BusinessField(
      name,
      label,
      type: BusinessInput.date,
      initial: value,
      required: required,
    );
    BusinessField check(String name, String label, dynamic value) =>
        BusinessField(
          name,
          label,
          type: BusinessInput.toggle,
          initial: value == true,
        );
    final fields = <BusinessField>[
      BusinessField(
        'target_month',
        'Tatsächlicher Abrechnungsmonat (JJJJ-MM)',
        initial: a['target_month'],
        required: true,
      ),
      date(
        'reviewed_as_of',
        'Tatsächlicher Prüfstand bis',
        a['reviewed_as_of'],
        required: true,
      ),
      check(
        'sole_continuous_commercial_minijob_confirmed',
        'Einziger durchgehender gewerblicher Minijob nach 2012 geprüft',
        a['sole_continuous_commercial_minijob_confirmed'],
      ),
      check(
        'no_old_age_or_other_exclusion_confirmed',
        'Keine Altersrenten- oder sonstigen Ausschlussfälle geprüft',
        a['no_old_age_or_other_exclusion_confirmed'],
      ),
      if (prior == null) ...[
        date(
          'exempt_from',
          'Bereits bestehende Befreiung ab',
          null,
          required: true,
        ),
        choice(
          'original_profile_id',
          'Ursprüngliches befreites Minijobprofil',
          choices: {
            for (final p in businessItems(s['profiles']).where(
              (p) =>
                  p['profile']['employment_kind'] == 'minijob' &&
                  p['profile']['minijob_rv_exempt'] == true,
            ))
              payrollRvSelection(
                p,
              ): '${businessDate(p['profile']['effective_from'])} · Fassung ${p['revision']}',
          },
          required: true,
        ),
        choice(
          'exemption_file_id',
          'Original zur bereits bestehenden Befreiung',
          required: true,
        ),
      ],
      check(
        'established_status_confirmed',
        'Bereits bestehende Befreiung anhand der Originale bestätigt',
        x['established_status_confirmed'],
      ),
      choice(
        'request_state',
        'Aufhebungsantrag tatsächlich eingegangen',
        initial: prior == null
            ? null
            : r.isEmpty
            ? 'none'
            : 'received',
        choices: {
          'none': 'Kein Aufhebungsantrag belegt',
          'received': 'Tatsächlicher Antrag belegt',
        },
        required: true,
      ),
      date(
        'received_on',
        'Antrag beim Arbeitgeber eingegangen am',
        r['received_on'],
      ),
      choice(
        'request_format',
        'Tatsächliche Antragsform',
        initial: r['request_format'],
        choices: {'written': 'Schriftlich', 'electronic': 'Elektronisch'},
      ),
      choice(
        'request_file_id',
        'Original des eingegangenen Antrags',
        initial: r['request_ref']?['id'],
      ),
      date(
        'notification_received_on',
        'Meldung bei der Minijob-Zentrale eingegangen am',
        r['notification_received_on'],
      ),
      choice(
        'notification_file_id',
        'Original zum Eingang der Meldung',
        initial: r['notification_ref']?['id'],
      ),
      choice(
        'authority_status',
        'Tatsächlicher Widerspruchsstand',
        initial: r['authority_status'],
        choices: {
          'not_notified': 'Meldung noch nicht belegt',
          'pending': 'Verfahren offen',
          'non_objection_verified': 'Nichtwiderspruch nach Fristprüfung belegt',
          'objected': 'Widerspruch belegt',
        },
      ),
      date(
        'objection_deadline_on',
        'Tatsächlich geprüfte Widerspruchsfrist bis',
        r['objection_deadline_on'],
      ),
      choice(
        'deadline_file_id',
        'Original der tatsächlichen Fristprüfung',
        initial: r['deadline_ref']?['id'],
      ),
      check(
        'deadline_review_confirmed',
        'Anwendbare Frist einschließlich Feiertagen fachlich geprüft',
        r['deadline_review_confirmed'],
      ),
      date(
        'authority_status_on',
        'Belegter Abschluss-/Widerspruchsstand vom',
        r['authority_status_on'],
      ),
      choice(
        'authority_file_id',
        'Original zum tatsächlichen Verfahrensstand',
        initial: r['authority_evidence_ref']?['id'],
      ),
      BusinessField(
        'procedure_note',
        'Prüfvermerk zum tatsächlichen Verfahren',
        type: BusinessInput.multiline,
        initial: r['review_note'],
      ),
      BusinessField(
        'review_note',
        'Prüfvermerk zum vollständigen RV-Verlauf',
        type: BusinessInput.multiline,
        initial: a['review_note'],
        required: true,
      ),
      if (prior != null)
        const BusinessField(
          'correction_reason',
          'Grund der Fortschreibung',
          type: BusinessInput.multiline,
          required: true,
        ),
    ];
    await showDialog<void>(
      context: context,
      builder: (context) {
        editor = context;
        return BusinessEditor(
          session: session,
          title: 'Minijob-RV anhand der Originale prüfen',
          fields: fields,
          readPermission: 'personnel.read',
          writePermission: 'personnel.approve',
          readAllowed: () => readable && captured == epoch,
          pendingKey: commandKey,
          saveLabel: 'RV-Wirkung unverbindlich prüfen',
          onSave: (values) async {
            await fresh(write: true);
            if (captured != epoch)
              fail('Der private RV-Entwurf wurde geschlossen.', 403);
            final b = payrollRvInput(s, values, previous: prior),
                p = payrollRvPreview(
                  await session.api.call(
                    session.path('$payrollRvPath/preview'),
                    payrollRvPreviewInput(b),
                  ),
                  b,
                );
            await fresh(write: true);
            if (!mounted || captured != epoch) return;
            setState(() {
              sources = s;
              previous = prior;
              body = {...b, 'preview_hash': p['preview_hash']};
              proof = p;
              accepted = false;
              error = null;
            });
          },
        );
      },
    );
    editor = null;
  }

  Widget summary(Map<String, dynamic> value) {
    final a = businessMap(value['details']?['assessment']),
        p = businessMap(value['plan']),
        r = businessMap(a['revocation']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          payrollRvStatuses[p['status']] ?? 'RV-Status ungeklärt',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Abrechnungsmonat · tatsächlicher Prüfstand'),
          subtitle: Text(
            '${a['target_month']} · ${businessDate(a['reviewed_as_of'])}',
          ),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Bereits bestehende Befreiung ab'),
          subtitle: Text(
            businessDate(a['established_exemption']?['effective_from']),
          ),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Antrag beim Arbeitgeber eingegangen'),
          subtitle: Text(
            r.isEmpty ? 'Kein Antrag belegt' : businessDate(r['received_on']),
          ),
        ),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Möglicher Wirkungsbeginn'),
          subtitle: Text(
            p['candidate_effective_from'] == null
                ? 'Kein Aufhebungsantrag'
                : businessDate(p['candidate_effective_from']),
          ),
        ),
        Text('${a['review_note'] ?? ''}'),
        const SizedBox(height: 12),
        const Text(
          'Diese Prüfung versendet keine Meldung und erzeugt weder ein Lohnprofil noch eine Zahlung. Den belegten RV-Status anschließend ausdrücklich im Lohnprofil auswählen.',
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!readable)
      return const Scaffold(
        body: Center(child: Text('Keine private Personalfreigabe.')),
      );
    final history = businessItems(sources?['history'] ?? const []);
    return Scaffold(
      appBar: AppBar(title: Text('Minijob-RV · ${widget.employee['name']}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Belegte bestehende RV-Befreiung und ein tatsächlicher Aufhebungsantrag im einzigen durchgehenden gewerblichen Minijob. Weitere Beschäftigungs- und Rentenfälle benötigen ihre eigene Prüfung.',
          ),
          const SizedBox(height: 12),
          if (error != null) Text(error!, key: const ValueKey('rv-error')),
          if (busy) const LinearProgressIndicator(),
          OutlinedButton(
            onPressed: busy ? null : load,
            child: const Text('Private RV-Quellen neu laden'),
          ),
          if (pending) ...[
            const Text(
              'Die ursprüngliche Speicherantwort ist offen. Zuerst denselben Auftrag klären.',
            ),
            FilledButton(
              onPressed: busy || !permitted ? null : repeat,
              child: const Text('Ursprüngliche RV-Anfrage unverändert prüfen'),
            ),
          ] else if (writable)
            FilledButton(
              onPressed: busy ? null : edit,
              child: Text(
                history.isEmpty
                    ? 'RV-Verlauf anhand der Originale aufnehmen'
                    : 'Prüfstand mit Originalen fortschreiben',
              ),
            ),
          if (proof != null && body != null) ...[
            const Divider(),
            const Text('Unverbindliche RV-Vorschau'),
            summary({'details': body!['details'], 'plan': proof!['plan']}),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: accepted,
              onChanged: busy || !writable
                  ? null
                  : (v) => setState(() => accepted = v == true),
              title: const Text(
                'Genau diesen Prüfstand und seine Originale ausdrücklich bestätigen',
              ),
            ),
            FilledButton(
              onPressed: accepted && writable && !busy && !pending
                  ? confirm
                  : null,
              child: const Text('Geprüften RV-Verlauf festhalten'),
            ),
          ],
          if (selected != null) ...[
            const Divider(),
            Text('Unveränderte Fassung ${selected!['revision']}'),
            summary(selected!),
            for (final f in businessItems(selected!['sources']['source_files']))
              OutlinedButton(
                onPressed: busy
                    ? null
                    : () => operate(() async {
                        await fresh();
                        await widget.onOriginal(f);
                      }),
                child: Text('Geschütztes Original: ${f['filename']}'),
              ),
          ],
          if (history.isNotEmpty) ...[
            const Divider(),
            const Text('Vollständige RV-Nachweishistorie'),
            for (final v in history)
              ExpansionTile(
                key: ValueKey('rv-history-${v['revision']}'),
                title: Text('Fassung ${v['revision']}'),
                children: [summary(v)],
              ),
          ],
        ],
      ),
    );
  }
}

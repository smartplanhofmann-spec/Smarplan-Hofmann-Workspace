import 'package:smartplan_office/api.dart';

import 'business_payroll_annual_basis_contract.dart';
import 'business_session.dart';
import 'business_widgets.dart';

typedef AnnualChoose = Future<Map<String, dynamic>?> Function(
  String title,
  List<BusinessField> fields,
);
Never _fail(String message) => throw ApiException(400, message);
String? _amount(dynamic v) => v is int
    ? '${v ~/ 100}.${(v.abs() % 100).toString().padLeft(2, '0')}'
    : null;
List<String> _ids(dynamic v) =>
    businessItems(v ?? []).map((v) => '${v['id']}').toList();

/// Structured source selection only; exact references are resolved by the
/// shared contract when the user requests the final server preview.
class PayrollAnnualForms {
  PayrollAnnualForms(this.sources, this.originals, this.choose);
  final Map<String, dynamic> sources;
  final List<String> originals;
  final AnnualChoose choose;
  BusinessField text(
    String name,
    String label, [
    dynamic initial,
    bool required = true,
  ]) => BusinessField(name, label, required: required, initial: initial);
  BusinessField date(
    String name,
    String label, [
    dynamic initial,
    bool required = true,
  ]) => BusinessField(
    name,
    label,
    type: BusinessInput.date,
    required: required,
    initial: initial,
  );
  BusinessField money(String name, String label, [dynamic initial]) =>
      BusinessField(
        name,
        '$label (EUR), auch bekannte 0',
        type: BusinessInput.decimal,
        required: true,
        initial: _amount(initial),
      );
  BusinessField count(String name, String label, [dynamic initial]) =>
      BusinessField(
        name,
        '$label, auch bekannte 0',
        type: BusinessInput.integer,
        required: true,
        initial: initial,
      );
  BusinessField choice(
    String name,
    String label,
    Map<String, String> options, [
    dynamic initial,
    bool required = true,
  ]) => BusinessField(
    name,
    label,
    type: BusinessInput.choice,
    required: required,
    initial: initial,
    choices: {if (required) '': 'Bitte ausdrücklich auswählen', ...options},
  );
  BusinessField yes(String name, String label, [dynamic initial]) => choice(
    name,
    label,
    const {'yes': 'Ja, belegt', 'no': 'Nein, belegt'},
    initial == true
        ? 'yes'
        : initial == false
        ? 'no'
        : null,
  );
  bool boolean(dynamic v) {
    if (!['yes', 'no'].contains(v))
      _fail('Jeden tatsächlichen Ja-/Nein-Sachverhalt ausdrücklich belegen.');
    return v == 'yes';
  }

  int number(dynamic v, int max) {
    if (v is! int || v < 0 || v > max)
      _fail('Eine tatsächliche Anzahl zwischen 0 und $max angeben.');
    return v;
  }

  List<Map<String, dynamic>> items(String collection, {List<String>? kinds}) =>
      businessItems(sources[collection])
          .where(
            (v) =>
                v['status'] != 'void' &&
                (kinds == null || kinds.contains(v['kind'])),
          )
          .toList();
  String label(Map<String, dynamic> v) {
    final d = businessMap(v['details']);
    return '${v['name'] ?? v['filename'] ?? d['original_payroll_reference'] ?? d['claim_reference'] ?? d['verification_note'] ?? v['month'] ?? d['month'] ?? v['kind'] ?? 'Quelle'} · Fassung ${v['revision']}';
  }

  BusinessField source(
    String name,
    String title,
    String collection, {
    List<String>? kinds,
    dynamic initial,
    bool multiple = false,
    bool required = true,
  }) => BusinessField(
    name,
    title,
    type: multiple ? BusinessInput.multiple : BusinessInput.choice,
    required: required,
    initial: multiple
        ? _ids(initial)
        : initial is Map
        ? initial['id']
        : initial,
    choices: {
      if (required && !multiple) '': 'Bitte ausdrücklich auswählen',
      for (final v in items(collection, kinds: kinds)) '${v['id']}': label(v),
    },
  );
  BusinessField file(
    String name,
    String title, {
    dynamic initial,
    bool multiple = false,
    bool required = true,
  }) => BusinessField(
    name,
    title,
    type: multiple ? BusinessInput.multiple : BusinessInput.choice,
    required: required,
    initial: multiple
        ? _ids(initial)
        : initial is Map
        ? initial['id']
        : initial,
    choices: {
      if (required && !multiple) '': 'Bitte ausdrücklich auswählen',
      for (final f in businessItems(
        sources['files'],
      ).where((f) => originals.contains(f['id'])))
        '${f['id']}': '${f['filename']}',
    },
  );
  Future<List<Map<String, dynamic>>?> rows(
    String title,
    int count,
    List<Map<String, dynamic>> old,
    List<BusinessField> Function(Map<String, dynamic>) fields,
    Map<String, dynamic> Function(Map<String, dynamic>) convert,
  ) async {
    final result = <Map<String, dynamic>>[];
    for (var i = 0; i < count; i++) {
      final row = await choose(
        '$title ${i + 1} von $count',
        fields(i < old.length ? old[i] : {}),
      );
      if (row == null) return null;
      result.add(convert(row));
    }
    return result;
  }

  Future<Map<String, dynamic>?> collect(
    String kind,
    Map<String, dynamic> old,
  ) async {
    if (kind == 'imported_period') return importedPeriod(old);
    if (kind == 'imported_one_off') return importedBonus(old);
    if (kind == 'annual_basis') return annualBasis(old);
    if (kind == 'one_off_earning') return earning(old);
    if (kind == 'annual_tax_forecast') return forecast(old);
    _fail('Unbekannte Art des Jahresnachweises.');
  }

  BusinessField section(dynamic initial) =>
      choice('section_key', 'Tatsächlicher Versicherungsabschnitt', const {
        'regular': 'Reguläre Beschäftigung',
        'minijob': 'Gewerblicher Minijob',
      }, initial);
  Future<Map<String, dynamic>?> importedPeriod(Map<String, dynamic> d) async {
    final p = businessMap(d['profile']),
        r = businessItems(d['running_receipts'] ?? []),
        b = businessMap(d['branches']);
    final value = await choose('Tatsächliche externe Lohnperiode', [
      date('period_start', 'Erster Tag der Originalperiode', d['period_start']),
      date('period_end', 'Letzter Tag der Originalperiode', d['period_end']),
      date(
        'employment_from',
        'Tatsächlicher Beschäftigungsbeginn',
        d['employment_from'],
      ),
      date(
        'employment_to',
        'Tatsächliches Beschäftigungsende, falls beendet',
        d['employment_to'],
        false,
      ),
      section(d['section_key']),
      money(
        'running_gross_minor',
        'Laufendes Originalbrutto',
        d['running_gross_minor'],
      ),
      money(
        'running_taxable_minor',
        'Individuell steuerpflichtiges laufendes Originalbrutto',
        d['running_taxable_minor'],
      ),
      text(
        'original_rule_version',
        'Ursprüngliches Abrechnungsverfahren',
        d['original_rule_version'],
      ),
      text(
        'original_rule_hash',
        'Nachgewiesener Original-Regelhash (64 Hexzeichen)',
        d['original_rule_hash'],
      ),
      text(
        'original_payroll_reference',
        'Eindeutige ursprüngliche Abrechnungsreferenz',
        d['original_payroll_reference'],
      ),
      file(
        'document_refs',
        'Konkrete Abrechnungsoriginale',
        initial: d['document_refs'],
        multiple: true,
      ),
      count(
        'receipt_count',
        'Anzahl tatsächlicher laufender Zuflüsse',
        d.isEmpty ? null : r.length,
      ),
    ]);
    if (value == null) return null;
    final profile = await choose('Historische tatsächliche Beitragsmerkmale', [
      choice(
        'scheme',
        'Originales Beitragsverfahren',
        payrollAnnualSchemes,
        p['scheme'],
      ),
      choice(
        'health_insurance',
        'Tatsächliche Krankenversicherung',
        payrollAnnualHealth,
        p['health_insurance'],
      ),
      text(
        'health_additional_percent',
        'Tatsächlicher historischer Zusatzbeitrag (%)',
        p['health_additional_percent'],
      ),
      text(
        'u1_percent',
        'Tatsächlicher historischer U1-Satz (%)',
        p['u1_percent'],
      ),
      text(
        'u2_percent',
        'Tatsächlicher historischer U2-Satz (%)',
        p['u2_percent'],
      ),
      yes('saxony', 'Sächsische Pflegeversicherungsaufteilung', p['saxony']),
      yes(
        'childless_surcharge',
        'Kinderlosenzuschlag ist belegt',
        p['childless_surcharge'],
      ),
      count(
        'care_child_discounts',
        'Zahl der berücksichtigten Kinderabschläge (0 bis 4)',
        p['care_child_discounts'],
      ),
      yes(
        'minijob_rv_exempt',
        'Minijob-Rentenversicherungsbefreiung ist belegt',
        p['minijob_rv_exempt'],
      ),
      yes(
        'pension_other_compulsory',
        'Weitere rentenversicherungspflichtige Beschäftigung ist belegt',
        p['pension_other_compulsory'],
      ),
    ]);
    if (profile == null) return null;
    final branches = <String, dynamic>{};
    for (final entry in payrollAnnualBranches.entries) {
      final prior = businessMap(b[entry.key]),
          intervals = businessItems(prior['eligible_intervals'] ?? []);
      final branch = await choose(
        '${entry.value}: tatsächliche bisherige Beitragsbasis',
        [
          money(
            'total_minor',
            'Bereits verbeitragte Gesamtbasis',
            prior['total_minor'],
          ),
          money(
            'employee_minor',
            'Bereits verbeitragte Arbeitnehmerbasis',
            prior['employee_minor'],
          ),
          count(
            'interval_count',
            'Zahl belegter beitragspflichtiger Intervalle',
            d.isEmpty ? null : intervals.length,
          ),
        ],
      );
      if (branch == null) return null;
      final periods = await rows(
        '${entry.value}: Beitragsintervall',
        number(branch['interval_count'], 62),
        intervals,
        (v) => [
          date('start', 'Tatsächlicher Beginn', v['start']),
          date('end', 'Tatsächliches Ende', v['end']),
          choice(
            'legal_reason',
            'Belegter Rechtsgrund',
            payrollAnnualIntervalReasons,
            v['legal_reason'],
          ),
          file(
            'evidence_ref',
            'Konkretes Intervalloriginal',
            initial: v['evidence_ref'],
          ),
        ],
        (v) => v,
      );
      if (periods == null) return null;
      branches[entry.key] = {
        'total_minor': payrollAnnualMoney(branch['total_minor']),
        'employee_minor': payrollAnnualMoney(branch['employee_minor']),
        'eligible_intervals': periods,
      };
    }
    final receipts = await rows(
      'Tatsächlicher laufender Zufluss',
      number(value['receipt_count'], 366),
      r,
      (v) => [
        date('received_on', 'Tatsächlicher Zuflusstag', v['received_on']),
        money(
          'taxable_minor',
          'Individuell steuerpflichtiger Betrag',
          v['taxable_minor'],
        ),
        file(
          'evidence_ref',
          'Original für diesen tatsächlichen Zufluss',
          initial: v['evidence_ref'],
        ),
      ],
      (v) => {...v, 'taxable_minor': payrollAnnualMoney(v['taxable_minor'])},
    );
    if (receipts == null) return null;
    return {
      for (final key in [
        'period_start',
        'period_end',
        'employment_from',
        'employment_to',
        'section_key',
        'original_rule_version',
        'original_rule_hash',
        'original_payroll_reference',
        'document_refs',
      ])
        key: value[key],
      'running_gross_minor': payrollAnnualMoney(value['running_gross_minor']),
      'running_taxable_minor': payrollAnnualMoney(
        value['running_taxable_minor'],
      ),
      'running_receipts': receipts,
      'branches': branches,
      'profile': {
        for (final key in ['scheme', 'health_insurance']) key: profile[key],
        for (final key in [
          'health_additional_percent',
          'u1_percent',
          'u2_percent',
        ])
          key: payrollAnnualRate(profile[key]),
        for (final key in [
          'saxony',
          'childless_surcharge',
          'minijob_rv_exempt',
          'pension_other_compulsory',
        ])
          key: boolean(profile[key]),
        'care_child_discounts': number(profile['care_child_discounts'], 4),
      },
    };
  }

  Future<Map<String, dynamic>?> importedBonus(Map<String, dynamic> d) async {
    final bases = businessMap(d['bases_minor']);
    final v = await choose('Bereits verarbeiteter externer Einmalbezug', [
      date('receipt_date', 'Tatsächlicher Zuflusstag', d['receipt_date']),
      money('amount_minor', 'Tatsächlicher Bruttobezug', d['amount_minor']),
      source(
        'assigned_period_ref',
        'Tatsächliche SV-Zuordnung im Original',
        'annual_facts',
        kinds: ['imported_period'],
        initial: d['assigned_period_ref'],
      ),
      section(d['section_key']),
      for (final branch in payrollAnnualBranches.entries)
        money(
          branch.key,
          '${branch.value}: tatsächlich verbeitragte Basis',
          bases[branch.key],
        ),
      text(
        'original_reference',
        'Eindeutige ursprüngliche Bonusreferenz',
        d['original_reference'],
      ),
      file(
        'document_refs',
        'Originale der tatsächlichen Abrechnung und Zahlung',
        initial: d['document_refs'],
        multiple: true,
      ),
    ]);
    if (v == null) return null;
    return {
      for (final key in [
        'receipt_date',
        'assigned_period_ref',
        'section_key',
        'original_reference',
        'document_refs',
      ])
        key: v[key],
      'amount_minor': payrollAnnualMoney(v['amount_minor']),
      'bases_minor': {
        for (final key in payrollAnnualBranches.keys)
          key: payrollAnnualMoney(v[key]),
      },
    };
  }

  Future<Map<String, dynamic>?> annualBasis(Map<String, dynamic> d) async {
    final gaps = businessItems(d['gaps'] ?? []);
    final v = await choose(
      'Vollständige Jahresbasis zum tatsächlichen Stichtag',
      [
        choice('year', 'Belegtes SV-Bezugsjahr', const {
          '2025': '2025',
          '2026': '2026',
        }, d['year']?.toString()),
        date('coverage_to', 'Tatsächlich gedeckt bis', d['coverage_to']),
        date(
          'as_of_date',
          'Tatsächlicher Beurteilungsstichtag',
          d['as_of_date'],
        ),
        source(
          'payroll_run_refs',
          'Alle einschlägigen internen Lohnläufe',
          'payroll_runs',
          initial: d['payroll_run_refs'],
          multiple: true,
          required: false,
        ),
        source(
          'payroll_payment_refs',
          'Tatsächliche Lohnzuflussnachweise',
          'payroll_payments',
          initial: d['payroll_payment_refs'],
          multiple: true,
          required: false,
        ),
        source(
          'imported_period_refs',
          'Alle einschlägigen externen Lohnperioden',
          'annual_facts',
          kinds: ['imported_period'],
          initial: d['imported_period_refs'],
          multiple: true,
          required: false,
        ),
        source(
          'imported_one_off_refs',
          'Alle schon zugeflossenen externen Einmalbezüge',
          'annual_facts',
          kinds: ['imported_one_off'],
          initial: d['imported_one_off_refs'],
          multiple: true,
          required: false,
        ),
        source(
          'current_calculation_case_ref',
          'Geplanter laufender Schlussmonat, falls noch nicht abgerechnet',
          'calculation_cases',
          kinds: ['calculation_case'],
          initial: d['current_calculation_case_ref'],
          required: false,
        ),
        count(
          'gap_count',
          'Anzahl ausdrücklich belegter Jahreslücken',
          d.isEmpty ? null : gaps.length,
        ),
        const BusinessField(
          'completeness_confirmed',
          'Ich bestätige die vollständigen tatsächlichen Jahresquellen ohne stillschweigende Nullmonate.',
          type: BusinessInput.toggle,
        ),
      ],
    );
    if (v == null) return null;
    if (v['completeness_confirmed'] != true)
      _fail('Vollständige Jahresdeckung ausdrücklich bestätigen.');
    final ranges = await rows(
      'Belegte Jahreslücke',
      number(v['gap_count'], 366),
      gaps,
      (old) => [
        date('start', 'Beginn der belegten Lücke', old['start']),
        date('end', 'Ende der belegten Lücke', old['end']),
        choice(
          'reason',
          'Tatsächlicher Lückengrund',
          payrollAnnualGapReasons,
          old['reason'],
        ),
        file(
          'evidence_ref',
          'Original für diese Lücke',
          initial: old['evidence_ref'],
        ),
      ],
      (v) => v,
    );
    if (ranges == null) return null;
    return {
      for (final key in [
        'coverage_to',
        'as_of_date',
        'payroll_run_refs',
        'payroll_payment_refs',
        'imported_period_refs',
        'imported_one_off_refs',
        'current_calculation_case_ref',
      ])
        key: v[key],
      'year': int.parse(v['year']),
      'gaps': ranges,
      'completeness_confirmed': true,
    };
  }

  Future<Map<String, dynamic>?> earning(Map<String, dynamic> d) async {
    final periods = businessItems(d['claim_periods'] ?? []);
    final v = await choose('Konkreter geplanter Einmalanspruch', [
      file('claim_key', 'Konkretes Anspruchsoriginal', initial: d['claim_key']),
      text(
        'claim_reference',
        'Nachgewiesene Anspruchsposition im Original',
        d['claim_reference'],
      ),
      date(
        'planned_receipt_date',
        'Ausdrücklich geplanter Zuflusstag',
        d['planned_receipt_date'],
      ),
      money('amount_minor', 'Belegter Bruttoanspruch', d['amount_minor']),
      section(d['section_key']),
      source(
        'employment_terms_refs',
        'Tatsächliche Beschäftigungsnachweise für den Anspruch',
        'facts',
        kinds: ['employment_terms'],
        initial: d['employment_terms_refs'],
        multiple: true,
      ),
      file(
        'document_refs',
        'Konkrete Anspruchsbelege',
        initial: d['document_refs'],
        multiple: true,
      ),
      count(
        'period_count',
        'Anzahl belegter Anspruchszeiträume',
        d.isEmpty ? null : periods.length,
      ),
      const BusinessField(
        'classification_confirmed',
        'Ich bestätige einen sonstigen Bezug und einmaliges Arbeitsentgelt; keine laufende Nachzahlung.',
        type: BusinessInput.toggle,
      ),
    ]);
    if (v == null) return null;
    if (v['classification_confirmed'] != true)
      _fail(
        'Die tatsächliche Steuer- und SV-Klassifikation ausdrücklich bestätigen.',
      );
    final ranges = await rows(
      'Tatsächlicher Anspruchszeitraum',
      number(v['period_count'], 366),
      periods,
      (old) => [
        date('start', 'Anspruch ab', old['start']),
        date('end', 'Anspruch bis', old['end']),
        file(
          'evidence_ref',
          'Original für diesen Zeitraum',
          initial: old['evidence_ref'],
        ),
      ],
      (v) => v,
    );
    if (ranges == null) return null;
    return {
      for (final key in [
        'claim_key',
        'claim_reference',
        'planned_receipt_date',
        'section_key',
        'employment_terms_refs',
        'document_refs',
      ])
        key: v[key],
      'amount_minor': payrollAnnualMoney(v['amount_minor']),
      'tax_classification': 'other_payment',
      'social_classification': 'one_off_remuneration',
      'claim_periods': ranges,
    };
  }

  Future<Map<String, dynamic>?> forecast(Map<String, dynamic> d) async {
    final remaining = businessItems(d['remaining_periods'] ?? []),
        previous = businessItems(d['previous_employers'] ?? []);
    final v = await choose(
      'Jahressteuergrundlage für den geplanten Einmalbezug',
      [
        source(
          'annual_basis_ref',
          'Passende belegte Jahresbasis',
          'annual_facts',
          kinds: ['annual_basis'],
          initial: d['annual_basis_ref'],
        ),
        date(
          'receipt_date',
          'Tatsächlicher Beurteilungs-/Zuflusstag',
          d['receipt_date'],
        ),
        source(
          'identity_ref',
          'Passender ELStAM-/Finanzamtsnachweis',
          'identities',
          kinds: ['identity'],
          initial: d['identity_ref'],
        ),
        source(
          'current_one_off_ref',
          'Aktueller geplanter Einmalanspruch',
          'annual_facts',
          kinds: ['one_off_earning'],
          initial: d['current_one_off_ref'],
        ),
        source(
          'other_tax_receipt_refs',
          'Weitere tatsächliche Jahreszuflüsse außerhalb der SV-Jahresbasis',
          'annual_facts',
          kinds: ['imported_period', 'imported_one_off'],
          initial: d['other_tax_receipt_refs'],
          multiple: true,
          required: false,
        ),
        count(
          'remaining_count',
          'Anzahl verbleibender ausdrücklich belegter Monate',
          d.isEmpty ? null : remaining.length,
        ),
        count(
          'previous_count',
          'Anzahl tatsächlicher früherer Arbeitgeber',
          d.isEmpty ? null : previous.length,
        ),
        file(
          'no_previous_employer_ref',
          'Ausdrücklicher Originalnachweis, wenn kein früherer Arbeitgeber vorliegt',
          initial: d['no_previous_employer_ref'],
          required: false,
        ),
      ],
    );
    if (v == null) return null;
    final future = await rows(
      'Belegter restlicher Jahresmonat',
      number(v['remaining_count'], 12),
      remaining,
      (old) => [
        text('month', 'Monat (JJJJ-MM)', old['month']),
        source(
          'employment_terms_ref',
          'Tatsächliche Beschäftigungsfassung',
          'facts',
          kinds: ['employment_terms'],
          initial: old['employment_terms_ref'],
        ),
        source(
          'agreement_refs',
          'Alle einschlägigen künftigen Entgeltvereinbarungen',
          'agreements',
          initial: old['agreement_refs'],
          multiple: true,
        ),
        source(
          'work_schedule_ref',
          'Belegter Sollplan, falls benötigt',
          'facts',
          kinds: ['work_schedule'],
          initial: old['work_schedule_ref'],
          required: false,
        ),
      ],
      (v) => v,
    );
    if (future == null) return null;
    final employers = await rows(
      'Tatsächlicher Vorarbeitgeber',
      number(v['previous_count'], 100),
      previous,
      (old) => [
        text(
          'employer_name',
          'Belegte Arbeitgeberbezeichnung',
          old['employer_name'],
        ),
        text(
          'employer_tax_number',
          'Belegte Arbeitgeber-Steuernummer',
          old['employer_tax_number'],
        ),
        date('start', 'Tatsächlicher Beginn', old['start']),
        date('end', 'Tatsächliches Ende', old['end']),
        money(
          'running_taxable_minor',
          'Belegter laufender steuerpflichtiger Lohn',
          old['running_taxable_minor'],
        ),
        money(
          'other_paid_minor',
          'Bereits erhaltene sonstige Bezüge',
          old['other_paid_minor'],
        ),
        file(
          'evidence_ref',
          'Konkreter Vorarbeitgebernachweis',
          initial: old['evidence_ref'],
        ),
      ],
      (v) => {
        ...v,
        'running_taxable_minor': payrollAnnualMoney(v['running_taxable_minor']),
        'other_paid_minor': payrollAnnualMoney(v['other_paid_minor']),
      },
    );
    if (employers == null) return null;
    return {
      for (final key in [
        'annual_basis_ref',
        'receipt_date',
        'identity_ref',
        'current_one_off_ref',
        'other_tax_receipt_refs',
        'no_previous_employer_ref',
      ])
        key: v[key],
      'remaining_periods': future,
      'previous_employers': employers,
    };
  }
}

import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_payroll_facts.dart' show payrollFactRef, payrollFactStates;
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const payrollTravelPolicyRule = 'de_2026_travel_tax_policy_v1';
const payrollTravelPolicyKey = 'payroll-travel-tax-policies';
const payrollTravelPolicyPath = '/payroll/travel-tax-policies';
const payrollTravelChurchMethods = {
  'simplified': 'Vereinfachtes Verfahren für sämtliche Empfänger',
  'evidence': 'Nachweisverfahren mit belegter Kirchenzugehörigkeit',
};
const payrollTravelChurchRegions = {
  'standard': 'Allgemeine Zuständigkeit des gewählten Bundeslands',
  'ni_ev_westfalen': 'Niedersachsen: Evangelische Kirche von Westfalen',
  'bw_bad_wimpfen_mainz':
      'Bad Wimpfen: römisch-katholische Zuständigkeit Mainz',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message, [int status = 400]) =>
    throw ApiException(status, message);
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
dynamic _ordered(dynamic value) {
  if (value is List) return value.map(_ordered).toList();
  if (value is Map) {
    final keys = value.keys.map((v) => '$v').toList()..sort();
    return {for (final key in keys) key: _ordered(value[key])};
  }
  return value;
}

bool _same(dynamic left, dynamic right) =>
    jsonEncode(_ordered(left)) == jsonEncode(_ordered(right));
String _text(dynamic value, String label) {
  if (value is! String ||
      value.trim().isEmpty ||
      value.trim().length > 3000 ||
      RegExp(r'[\x00-\x1f\x7f]').hasMatch(value)) {
    _fail('$label vollständig belegen.');
  }
  return value.trim();
}

String _date(dynamic value) {
  if (value is! String || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) {
    _fail('Einen tatsächlichen vollständigen Kalendertag angeben.');
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null || parsed.toIso8601String().substring(0, 10) != value) {
    _fail('Ein gültiges Kalendertagsdatum angeben.');
  }
  return value;
}

Map<String, dynamic> payrollTravelTaxPolicyDetails(dynamic raw) {
  final value = businessMap(raw);
  final from = _date(value['filing_period_from']),
      to = _date(value['filing_period_to']);
  final first = DateTime.parse(from), last = DateTime.parse(to);
  String lastOf(int month) =>
      DateTime(2026, month + 1, 0).toIso8601String().substring(0, 10);
  final wholeMonth = first.day == 1 && to == lastOf(first.month),
      quarter =
          first.day == 1 &&
          [1, 4, 7, 10].contains(first.month) &&
          to == lastOf(first.month + 2),
      year = from == '2026-01-01' && to == '2026-12-31';
  if (first.year != 2026 ||
      last.year != 2026 ||
      !(wholeMonth || quarter || year)) {
    _fail(
      'Einen vollständigen belegten Anmeldemonat, ein Quartal oder das Jahr 2026 angeben.',
    );
  }
  if (!payrollFactStates.containsKey(value['federal_state']) ||
      !payrollTravelChurchMethods.containsKey(value['church_method']) ||
      !payrollTravelChurchRegions.containsKey(value['church_rate_region']) ||
      value['church_rate_region'] == 'ni_ev_westfalen' &&
          value['federal_state'] != 'NI' ||
      value['church_rate_region'] == 'bw_bad_wimpfen_mainz' &&
          value['federal_state'] != 'BW' ||
      value['church_method_applies_to_all'] != true ||
      value['employer_bears_tax'] is! bool) {
    _fail(
      'Betriebsstätte, Zuständigkeit, einheitliches Verfahren und Kostenübernahme ausdrücklich belegen.',
    );
  }
  final result = <String, dynamic>{
    'filing_period_from': from,
    'filing_period_to': to,
    'federal_state': value['federal_state'],
    'church_method': value['church_method'],
    'church_rate_region': value['church_rate_region'],
    'church_method_applies_to_all': true,
    'employer_bears_tax': value['employer_bears_tax'],
    'verification_note': _text(
      value['verification_note'],
      'Betriebliche Steuerentscheidung',
    ),
  };
  if (value.keys.any((key) => !result.containsKey(key))) {
    _fail('Unbekannte Angaben in der betrieblichen Steuerentscheidung.');
  }
  return result;
}

List<String> _originals(dynamic rawFiles, dynamic rawIds) {
  if (rawFiles is! List ||
      rawIds is! List ||
      rawIds.isEmpty ||
      rawIds.length > 100 ||
      rawIds.toSet().length != rawIds.length) {
    _fail(
      'Konkrete geschützte Originale der betrieblichen Entscheidung auswählen.',
    );
  }
  final files = businessItems(rawFiles), ids = <String>[];
  for (final id in rawIds) {
    final matches = files.where((file) => file['id'] == id).toList();
    if (id is! String || !_id.hasMatch(id) || matches.length != 1) {
      _fail('Die tatsächliche geschützte Originalfassung fehlt.');
    }
    final file = matches.single;
    if (file['purpose'] != 'personnel' ||
        !_id.hasMatch('${file['employee_id']}') ||
        !_hash.hasMatch('${file['sha256']}') ||
        !_hash.hasMatch('${file['content_hash']}') ||
        file['size'] is! int ||
        file['size'] < 1) {
      _fail('Die tatsächliche geschützte Originalfassung fehlt.');
    }
    ids.add(id);
  }
  return ids..sort();
}

Map<String, dynamic> payrollTravelTaxPolicyRecord(dynamic raw) {
  final value = businessMap(raw);
  payrollFactRef(value);
  final details = payrollTravelTaxPolicyDetails(value['details']),
      sources = businessMap(value['sources']);
  if (value['employee_id'] != null ||
      !value.containsKey('employee_id') ||
      value['kind'] != 'travel_tax_policy' ||
      value['rule_version'] != payrollTravelPolicyRule ||
      value['source_contract_version'] is! int ||
      value['source_contract_version'] != 1 ||
      !['active', 'void'].contains(value['status']) ||
      value['plan'] != null ||
      !value.containsKey('plan') ||
      sources['schema_version'] is! int ||
      sources['schema_version'] != 1 ||
      !_same(sources['policy'], details) ||
      !_same(value['details'], details) ||
      value['effective_from'] != details['filing_period_from'] ||
      value['effective_to'] != details['filing_period_to'] ||
      !_hash.hasMatch('${value['source_hash']}') ||
      !_hash.hasMatch('${value['preview_hash']}') ||
      (value['revision'] == 1
          ? value['previous_hash'] != null
          : !_hash.hasMatch('${value['previous_hash']}')) ||
      !_same(
        _originals(sources['source_files'], value['source_file_ids']),
        value['source_file_ids'],
      ) ||
      !_same(
        businessItems(sources['source_files'])
            .map((file) => file['id'])
            .toList()
          ..sort(),
        value['source_file_ids'],
      )) {
    _fail(
      'Die Steuerentscheidung ist nicht an ihre ursprüngliche betriebliche Fassung gebunden.',
    );
  }
  return value;
}

Map<String, dynamic> payrollTravelTaxPolicySources(dynamic raw) {
  final value = businessMap(raw);
  if (!value.containsKey('employee_id') ||
      value['employee_id'] != null ||
      value['files'] is! List ||
      value['file_references'] is! List ||
      value['policies'] is! List ||
      [
        'can_write',
        'can_approve',
        'writes_enabled',
      ].any((key) => value[key] is! bool) ||
      value['files'].length != value['file_references'].length) {
    _fail('Der betriebliche Originalkatalog ist unvollständig.');
  }
  final files = <String>{}, references = <String>{}, policies = <String>{};
  for (final file in businessItems(value['files'])) {
    _originals([file], [file['id']]);
    if (!files.add(file['id']))
      _fail('Eine Originalfassung wurde mehrfach geliefert.');
  }
  for (final ref in businessItems(value['file_references'])) {
    payrollFactRef(ref);
    final file = businessItems(value['files'])
        .where((file) => file['id'] == ref['id'])
        .toList();
    if (ref['revision'] != 1 ||
        !references.add(ref['id']) ||
        file.length != 1 ||
        file.single['content_hash'] != ref['content_hash']) {
      _fail(
        'Originalreferenz und geschützter Dateinachweis widersprechen sich.',
      );
    }
  }
  for (final policy in businessItems(value['policies'])) {
    payrollTravelTaxPolicyRecord(policy);
    if (!policies.add(policy['id']))
      _fail('Eine Steuerentscheidung wurde mehrfach geliefert.');
  }
  return value;
}

Map<String, dynamic> payrollTravelTaxPolicyInput(
  Map<String, dynamic> sources,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  payrollTravelTaxPolicySources(sources);
  if (previous != null) payrollTravelTaxPolicyRecord(previous);
  final details = payrollTravelTaxPolicyDetails(values['details']);
  if (previous != null &&
      [
        'filing_period_from',
        'filing_period_to',
        'federal_state',
        'church_rate_region',
      ].any((key) => details[key] != previous['details'][key])) {
    _fail(
      'Zeitraum und Betriebsstätten-Zuständigkeit der ursprünglichen Entscheidung bleiben bei einer Korrektur erhalten.',
    );
  }
  return {
    'employee_id': null,
    'employee_revision': null,
    'kind': 'travel_tax_policy',
    'rule_version': payrollTravelPolicyRule,
    'source_contract_version': 1,
    'revision': previous?['revision'] ?? 0,
    'status': 'active',
    'details': details,
    'source_file_ids': _originals(sources['files'], values['source_file_ids']),
    'confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': _text(values['correction_reason'], 'Korrekturgrund'),
    },
  };
}

Map<String, dynamic> payrollTravelTaxPolicyPreviewInput(
  Map<String, dynamic> body,
) => _copy({
  for (final key in [
    'employee_id',
    'employee_revision',
    'kind',
    'rule_version',
    'source_contract_version',
    'details',
    'source_file_ids',
  ])
    key: body[key],
});

Map<String, dynamic> payrollTravelTaxPolicyPreview(
  dynamic raw,
  Map<String, dynamic> body,
) {
  final value = businessMap(raw),
      source = businessMap(value['source_snapshot']);
  if (!value.containsKey('employee_id') ||
      value['employee_id'] != null ||
      value['kind'] != 'travel_tax_policy' ||
      !value.containsKey('plan') ||
      value['plan'] != null ||
      source['schema_version'] is! int ||
      source['schema_version'] != 1 ||
      !_same(source['policy'], body['details']) ||
      !_same(
        _originals(source['source_files'], body['source_file_ids']),
        body['source_file_ids'],
      ) ||
      !_same(
        businessItems(source['source_files']).map((v) => v['id']).toList()
          ..sort(),
        body['source_file_ids'],
      ) ||
      !_hash.hasMatch('${value['source_hash']}') ||
      !_hash.hasMatch('${value['preview_hash']}') ||
      [
        'can_confirm',
        'can_calculate',
        'can_write',
        'can_approve',
        'writes_enabled',
      ].any((key) => value[key] is! bool)) {
    _fail(
      'Die Vorschau gehört nicht zur gewählten betrieblichen Steuerentscheidung.',
    );
  }
  return value;
}

void Function(dynamic) payrollTravelTaxPolicyValidator(
  Map<String, dynamic> body, {
  Map<String, dynamic>? previous,
  Map<String, dynamic>? preview,
}) {
  final frozen = _copy(body),
      prior = previous == null ? null : _copy(previous),
      proof = preview == null ? null : _copy(preview);
  return (raw) {
    final value = payrollTravelTaxPolicyRecord(raw);
    if (value['revision'] != frozen['revision'] + 1 ||
        frozen['id'] != null && value['id'] != frozen['id'] ||
        value['previous_hash'] != prior?['content_hash'] ||
        value['status'] != frozen['status'] ||
        !_same(value['details'], frozen['details']) ||
        !_same(value['source_file_ids'], frozen['source_file_ids']) ||
        value['preview_hash'] != frozen['preview_hash'] ||
        value['correction_reason'] != (frozen['correction_reason'] ?? '') ||
        proof != null &&
            (!_same(value['sources'], proof['source_snapshot']) ||
                value['source_hash'] != proof['source_hash']) ||
        frozen['status'] == 'void' &&
            (prior == null ||
                !_same(value['sources'], prior['sources']) ||
                value['source_hash'] != prior['source_hash'])) {
      _fail(
        'Die Antwort bestätigt nicht den unveränderten geprüften Steuerauftrag. Die ursprüngliche Anfrage bleibt erhalten.',
        502,
      );
    }
  };
}

typedef PayrollTravelPolicyOriginal = Future<void> Function(
  Map<String, dynamic> employee,
  Map<String, dynamic> file,
);

Future<Map<String, dynamic>?> showPayrollTravelTaxPolicies(
  BuildContext context, {
  required BusinessSession session,
  PayrollTravelPolicyOriginal? onOriginal,
  bool selectable = true,
}) => Navigator.of(context).push<Map<String, dynamic>>(
  MaterialPageRoute(
    builder: (_) => BusinessPayrollTravelTaxPoliciesPage(
      session: session,
      onOriginal: onOriginal,
      selectable: selectable,
    ),
  ),
);

class BusinessPayrollTravelTaxPoliciesPage extends StatefulWidget {
  const BusinessPayrollTravelTaxPoliciesPage({
    super.key,
    required this.session,
    this.onOriginal,
    this.selectable = true,
  });
  final BusinessSession session;
  final PayrollTravelPolicyOriginal? onOriginal;
  final bool selectable;
  @override
  State<BusinessPayrollTravelTaxPoliciesPage> createState() =>
      _BusinessPayrollTravelTaxPoliciesPageState();
}

class _BusinessPayrollTravelTaxPoliciesPageState
    extends State<BusinessPayrollTravelTaxPoliciesPage>
    with WidgetsBindingObserver {
  BusinessSession get session => widget.session;
  Map<String, dynamic>? sources, selected, preview, previewBody, previous;
  List<Map<String, dynamic>> history = [];
  String? error;
  bool loading = false, busy = false, historical = false;
  int epoch = 0;
  Object? generation;
  bool get readable =>
      session.allowed &&
      session.projectId == null &&
      session.hasFeature('payroll_calculation_cases') &&
      session.hasModule('payroll_calculation_cases') &&
      session.can('personnel.read');
  bool get permitted =>
      readable && !session.readonly && session.can('personnel.approve');
  bool get writable =>
      permitted &&
      session.sectionEnabled('personnel') &&
      sources?['can_approve'] == true &&
      sources?['writes_enabled'] == true;
  Map<String, dynamic>? get pending => session.pendingCommandValues(
    payrollTravelPolicyKey,
    path: payrollTravelPolicyPath,
  );
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

  void clear() {
    sources = selected = preview = previewBody = previous = null;
    history = [];
    loading = false;
  }

  void changed() {
    if (!mounted) return;
    if (!readable || generation != null && generation != session.generation) {
      epoch++;
      setState(() {
        clear();
        generation = session.generation;
      });
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if ((state == AppLifecycleState.hidden ||
            state == AppLifecycleState.paused) &&
        mounted) {
      epoch++;
      setState(clear);
    }
  }

  void failed(Object failure) {
    if (!mounted) return;
    setState(() {
      error = failure is ApiException
          ? failure.message
          : 'Die betriebliche Steuerentscheidung konnte nicht geprüft werden.';
      if (failure is ApiException && [401, 403, 404].contains(failure.status))
        clear();
    });
  }

  Future<Map<String, dynamic>> fresh({
    bool write = false,
    bool replay = false,
  }) async {
    await session.load();
    if (!mounted || !readable || session.error != null || write && !permitted) {
      _fail('Aktuelle globale Personal-Lese- und Freigaberechte fehlen.', 403);
    }
    final stamp = session.generation;
    final value = payrollTravelTaxPolicySources(
      await session.read('$payrollTravelPolicyPath/sources'),
    );
    if (!mounted ||
        !readable ||
        stamp != session.generation ||
        write && (!permitted || value['can_approve'] != true)) {
      _fail(
        'Die private Ansicht oder Freigabeberechtigung wurde geändert.',
        403,
      );
    }
    if (write &&
        !replay &&
        (!session.sectionEnabled('personnel') ||
            value['writes_enabled'] != true)) {
      _fail(
        'Neue Steuerentscheidungen sind im pausierten Personalbereich gesperrt.',
        423,
      );
    }
    return value;
  }

  Future<void> load() async {
    if (loading) return;
    final ticket = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await fresh();
      if (mounted && ticket == epoch)
        setState(() {
          sources = value;
          generation = session.generation;
        });
    } catch (failure) {
      if (ticket == epoch) failed(failure);
    } finally {
      if (mounted && ticket == epoch) setState(() => loading = false);
    }
  }

  Future<void> act(Future<void> Function() work) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await work();
    } catch (failure) {
      failed(failure);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> inspect(Map<String, dynamic> value, {bool old = false}) async {
    payrollTravelTaxPolicyRecord(value);
    final current = await fresh();
    if (!mounted) return;
    setState(() {
      sources = current;
      selected = _copy(value);
      historical = old;
      preview = previewBody = previous = null;
      history = [];
    });
  }

  Future<void> save(
    Map<String, dynamic> body, {
    Map<String, dynamic>? prior,
    Map<String, dynamic>? proof,
  }) async {
    final original = pending;
    if (original != null) {
      if (!_same(original, body)) {
        _fail(
          'Nur den unveränderten ursprünglichen Steuerauftrag erneut prüfen.',
          409,
        );
      }
      await fresh(write: true, replay: true);
      final value = payrollTravelTaxPolicyRecord(
        await session.repeatPayrollTravelTaxPolicyCommand(),
      );
      if (mounted && readable) await inspect(value);
      return;
    }
    await fresh(write: true);
    if (pending != null)
      _fail('Zuerst den ursprünglichen offenen Steuerauftrag klären.', 409);
    final value = payrollTravelTaxPolicyRecord(
      await session.command(
        payrollTravelPolicyKey,
        payrollTravelPolicyPath,
        body,
        validateResult: payrollTravelTaxPolicyValidator(
          body,
          previous: prior,
          preview: proof,
        ),
      ),
    );
    if (mounted && readable) await inspect(value);
  }

  Future<void> repeat() => act(() async {
    await fresh(write: true, replay: true);
    await session.repeatPayrollTravelTaxPolicyCommand();
    if (mounted && readable) {
      setState(() {
        preview = previewBody = previous = null;
      });
      await load();
    }
  });
  Future<void> edit([Map<String, dynamic>? prior]) async {
    if (busy || pending != null) return;
    Map<String, dynamic> page;
    try {
      page = await fresh(write: true);
    } catch (failure) {
      failed(failure);
      return;
    }
    if (!mounted) return;
    final details = businessMap(prior?['details']);
    final fields = <BusinessField>[
      const BusinessField(
        'filing_period_from',
        'Tatsächlicher Anmeldezeitraum ab',
        type: BusinessInput.date,
        required: true,
      ),
      const BusinessField(
        'filing_period_to',
        'Tatsächlicher Anmeldezeitraum bis',
        type: BusinessInput.date,
        required: true,
      ),
      const BusinessField(
        'federal_state',
        'Bundesland der lohnsteuerlichen Betriebsstätte',
        type: BusinessInput.choice,
        required: true,
        choices: payrollFactStates,
      ),
      const BusinessField(
        'church_method',
        'Einheitliches Kirchensteuerverfahren',
        type: BusinessInput.choice,
        required: true,
        choices: payrollTravelChurchMethods,
      ),
      const BusinessField(
        'church_rate_region',
        'Belegte kirchensteuerliche Zuständigkeit',
        type: BusinessInput.choice,
        required: true,
        choices: payrollTravelChurchRegions,
      ),
      const BusinessField(
        'cost_bearer',
        'Wirtschaftliche Übernahme der Steuerkosten',
        type: BusinessInput.choice,
        required: true,
        choices: {
          'employer': 'Arbeitgeber übernimmt die Steuerkosten',
          'employee':
              'Arbeitnehmerabzug nur mit gesondertem Vereinbarungsnachweis',
        },
      ),
      BusinessField(
        'source_file_ids',
        'Geschützte Originale der betrieblichen Entscheidung',
        type: BusinessInput.multiple,
        required: true,
        choices: {
          for (final file in businessItems(page['files']))
            '${file['id']}': '${file['filename']}',
        },
      ),
      const BusinessField(
        'verification_note',
        'Nachvollziehbarer betrieblicher Prüfvermerk',
        required: true,
      ),
      const BusinessField(
        'church_method_applies_to_all',
        'Dieses Verfahren gilt einheitlich für den gesamten Anmeldezeitraum und Tatbestand.',
        type: BusinessInput.toggle,
      ),
      if (prior != null)
        const BusinessField(
          'correction_reason',
          'Belegter Korrekturgrund',
          required: true,
        ),
    ];
    Map<String, dynamic>? body, proof;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: prior == null
            ? 'Betriebliche Steuerentscheidung erfassen'
            : 'Betriebliche Steuerentscheidung korrigieren',
        fields: fields,
        initial: {
          ...details,
          'source_file_ids': prior?['source_file_ids'] ?? <String>[],
          'church_method_applies_to_all': false,
          if (details['employer_bears_tax'] is bool)
            'cost_bearer': details['employer_bears_tax'] == true
                ? 'employer'
                : 'employee',
        },
        readPermission: 'personnel.read',
        writePermission: 'personnel.approve',
        readAllowed: () => readable,
        saveLabel: 'Betriebliche Entscheidung unverbindlich prüfen',
        onSave: (values) async {
          final current = await fresh(write: true);
          if (!['employer', 'employee'].contains(values['cost_bearer']))
            _fail('Kostenübernahme ausdrücklich wählen.');
          body = payrollTravelTaxPolicyInput(current, {
            ...values,
            'details': {
              for (final key in [
                'filing_period_from',
                'filing_period_to',
                'federal_state',
                'church_method',
                'church_rate_region',
                'church_method_applies_to_all',
                'verification_note',
              ])
                key: values[key],
              'employer_bears_tax': values['cost_bearer'] == 'employer',
            },
          }, previous: prior);
          final raw = await session.api.call(
            session.path('$payrollTravelPolicyPath/preview'),
            payrollTravelTaxPolicyPreviewInput(body!),
          );
          proof = payrollTravelTaxPolicyPreview(raw, body!);
        },
      ),
    );
    if (mounted && readable && body != null && proof != null)
      setState(() {
        sources = page;
        preview = proof;
        previewBody = {...body!, 'preview_hash': proof!['preview_hash']};
        previous = prior;
        selected = null;
        history = [];
      });
  }

  Future<void> confirm() async {
    if (preview == null || previewBody == null || busy) return;
    final body = _copy(previewBody),
        proof = _copy(preview),
        prior = previous == null ? null : _copy(previous);
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Betriebliche Steuerentscheidung bestätigen',
        fields: const [
          BusinessField(
            'confirmed',
            'Ich bestätige die belegten Originale und die einheitliche betriebliche Entscheidung.',
            type: BusinessInput.toggle,
          ),
        ],
        readPermission: 'personnel.read',
        writePermission: 'personnel.approve',
        readAllowed: () => readable,
        saveLabel: 'Geprüfte Entscheidung festhalten',
        pendingKey: payrollTravelPolicyKey,
        onSave: (values) async {
          if (values['confirmed'] != true)
            _fail('Die betriebliche Entscheidung ausdrücklich bestätigen.');
          if (proof['can_confirm'] != true)
            _fail('Diese Vorschau kann noch nicht bestätigt werden.');
          await save(body, prior: prior, proof: proof);
        },
      ),
    );
  }

  Future<void> voidPolicy(Map<String, dynamic> prior) async {
    await fresh(write: true);
    if (!mounted) return;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Fälschliche betriebliche Entscheidung aufheben',
        fields: const [
          BusinessField(
            'correction_reason',
            'Belegter Aufhebungsgrund',
            required: true,
          ),
          BusinessField(
            'confirmed',
            'Ich bestätige die Aufhebung. Frühere Lohn- und Steuererfassungen bleiben erhalten.',
            type: BusinessInput.toggle,
          ),
        ],
        readPermission: 'personnel.read',
        writePermission: 'personnel.approve',
        readAllowed: () => readable,
        saveLabel: 'Entscheidung belegt aufheben',
        pendingKey: payrollTravelPolicyKey,
        onSave: (values) async {
          if (values['confirmed'] != true)
            _fail('Aufhebung ausdrücklich bestätigen.');
          await save({
            ...payrollTravelTaxPolicyPreviewInput(prior),
            'employee_revision': null,
            'id': prior['id'],
            'revision': prior['revision'],
            'status': 'void',
            'preview_hash': prior['preview_hash'],
            'confirmed': true,
            'correction_reason': _text(
              values['correction_reason'],
              'Aufhebungsgrund',
            ),
          }, prior: prior);
        },
      ),
    );
  }

  Widget line(String label, String value) =>
      ListTile(dense: true, title: Text(label), subtitle: Text(value));
  Widget detailsView(Map<String, dynamic> details) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      line(
        'Anmeldezeitraum',
        '${businessDate(details['filing_period_from'])} – ${businessDate(details['filing_period_to'])}',
      ),
      line(
        'Lohnsteuerliche Betriebsstätte',
        payrollFactStates[details['federal_state']]!,
      ),
      line(
        'Kirchensteuerverfahren',
        payrollTravelChurchMethods[details['church_method']]!,
      ),
      line(
        'Zuständigkeit',
        payrollTravelChurchRegions[details['church_rate_region']]!,
      ),
      line(
        'Wirtschaftliche Steuerkosten',
        details['employer_bears_tax'] == true
            ? 'Arbeitgeber übernimmt die Steuerkosten'
            : 'Arbeitnehmerabzug nur mit eigener belegter Vereinbarung',
      ),
      line('Prüfvermerk', '${details['verification_note']}'),
    ],
  );
  Future<void> select(Map<String, dynamic> value) async {
    final current = await fresh();
    final matches = businessItems(current['policies'])
        .where((item) => item['id'] == value['id'])
        .toList();
    if (matches.length != 1 ||
        matches.single['status'] != 'active' ||
        !_same(payrollFactRef(matches.single), payrollFactRef(value)))
      _fail(
        'Die Entscheidung wurde inzwischen geändert. Aktuelle Fassung neu auswählen.',
        409,
      );
    if (mounted) Navigator.of(context).pop(_copy(matches.single));
  }

  Widget recordView(Map<String, dynamic> value, {bool old = false}) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Fassung ${value['revision']} · ${value['status'] == 'active' ? 'Aktiv' : 'Aufgehoben'}',
          ),
          detailsView(businessMap(value['details'])),
          for (final file in businessItems(value['sources']['source_files']))
            widget.onOriginal == null
                ? line('Geschütztes Original', '${file['filename']}')
                : TextButton(
                    onPressed: busy
                        ? null
                        : () => act(() async {
                            await fresh();
                            await widget.onOriginal!({
                              'id': file['employee_id'],
                            }, file);
                          }),
                    child: Text('Geschütztes Original: ${file['filename']}'),
                  ),
          if (!old)
            TextButton(
              onPressed: busy
                  ? null
                  : () => act(() async {
                      await fresh();
                      final raw = businessMap(
                        await session.read(
                          '$payrollTravelPolicyPath/${value['id']}/history',
                        ),
                      );
                      if (raw['items'] is! List)
                        _fail('Die Entscheidungshistorie fehlt.');
                      final items = businessItems(raw['items']);
                      for (var i = 0; i < items.length; i++) {
                        final item = payrollTravelTaxPolicyRecord(items[i]);
                        if (item['id'] != value['id'] ||
                            item['revision'] != i + 1 ||
                            item['previous_hash'] !=
                                (i == 0 ? null : items[i - 1]['content_hash']))
                          _fail(
                            'Die Historie gehört nicht vollständig zur ausgewählten Entscheidung.',
                          );
                      }
                      if (mounted && readable) setState(() => history = items);
                    }),
              child: const Text('Entscheidungshistorie öffnen'),
            ),
          if (!old && writable && pending == null) ...[
            TextButton(
              onPressed: busy ? null : () => edit(value),
              child: const Text('Entscheidung korrigieren'),
            ),
            if (value['status'] == 'active')
              TextButton(
                onPressed: busy ? null : () => act(() => voidPolicy(value)),
                child: const Text('Fälschliche Entscheidung aufheben'),
              ),
          ],
          if (!old && value['status'] == 'active' && widget.selectable)
            FilledButton(
              onPressed: busy ? null : () => act(() => select(value)),
              child: const Text('Diese aktuelle Entscheidung auswählen'),
            ),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Betriebliche Reise-Pauschalsteuer'),
      actions: [
        IconButton(
          onPressed: busy || loading ? null : load,
          tooltip: 'Rechte und Quellen aktualisieren',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: !readable
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: BusinessEmpty(
              'Steuerentscheidungen nicht freigegeben',
              'Diese privaten Nachweise benötigen aktuelle globale Personal-Leserechte.',
            ),
          )
        : ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Notice(
                'Betriebliche Entscheidung über die 25%-Pauschalierung zusätzlicher Reise-Verpflegung. Der Anmeldezeitraum und die Betriebsstätte müssen tatsächlich belegt sein.',
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
                        const Text('Steuerentscheidung noch offen'),
                        const Notice(
                          'Der Auftrag kann bereits gespeichert sein. Es wird nur der unveränderte ursprüngliche Auftrag erneut geprüft.',
                        ),
                        if (permitted)
                          FilledButton(
                            onPressed: busy ? null : repeat,
                            child: const Text(
                              'Ursprünglichen Steuerauftrag erneut senden',
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              if (preview != null) ...[
                Text(
                  'Betriebliche Steuerentscheidung prüfen',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                detailsView(businessMap(previewBody!['details'])),
                const Notice(
                  'Die tatsächliche Steuererfassung erfolgt erst mit einem gesondert bestätigten Lohnabschluss.',
                ),
                if (writable && pending == null)
                  FilledButton(
                    onPressed: busy ? null : confirm,
                    child: const Text('Geprüfte Entscheidung festhalten'),
                  ),
              ],
              if (selected != null) recordView(selected!, old: historical),
              for (final item in history) recordView(item, old: true),
              if (writable && pending == null)
                FilledButton(
                  onPressed: busy ? null : () => edit(),
                  child: const Text('Betriebliche Steuerentscheidung erfassen'),
                ),
              for (final item in businessItems(
                sources?['policies'] ?? const [],
              ))
                Card(
                  child: ListTile(
                    title: Text(
                      '${businessDate(item['effective_from'])} – ${businessDate(item['effective_to'])}',
                    ),
                    subtitle: Text(
                      '${payrollFactStates[item['details']['federal_state']]} · Fassung ${item['revision']}',
                    ),
                    trailing: TextButton(
                      onPressed: busy ? null : () => act(() => inspect(item)),
                      child: const Text('Entscheidung öffnen'),
                    ),
                  ),
                ),
              if (sources != null &&
                  businessItems(sources!['policies']).isEmpty)
                const Notice(
                  'Noch keine belegte betriebliche Steuerentscheidung vorhanden.',
                ),
            ],
          ),
  );
}

import 'dart:convert';

import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'design.dart';
import 'offline_vault.dart' show offlineId;
import 'online_command_journal.dart';

final _id = RegExp(r'^[a-f0-9]{32}$');
Never _fail(String message, [int status = 400]) =>
    throw ApiException(status, message);
Map<String, dynamic> _copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

BigInt materialReturnQuantity(dynamic value) {
  if (value is! String || !RegExp(r'^\d{1,12}(?:\.\d{1,4})?$').hasMatch(value))
    _fail(
      'Eine genaue positive Menge mit höchstens vier Nachkommastellen angeben.',
    );
  final parts = value.split('.');
  final result =
      BigInt.parse(parts[0]) * BigInt.from(10000) +
      BigInt.parse((parts.length == 1 ? '' : parts[1]).padRight(4, '0'));
  if (result <= BigInt.zero) _fail('Die Rückgabemenge muss positiv sein.');
  return result;
}

String materialReturnQuantityText(BigInt value) =>
    '${value ~/ BigInt.from(10000)}.${(value % BigInt.from(10000)).toString().padLeft(4, '0')}';

Map<String, dynamic> _issueIdentity(Map<String, dynamic> value) => {
  for (final key in [
    'id',
    'kind',
    'article_id',
    'project_id',
    'from_location_id',
    'to_location_id',
    'sequence_number',
    'quantity',
  ])
    key: value[key],
};

/// Quantities stay exact; no catalog price or client valuation is used.
List<Map<String, dynamic>> materialReturnOptions(
  dynamic raw, {
  String? projectId,
}) {
  if (raw is! List) _fail('Die vollständigen Lagerbewegungen fehlen.');
  final movements = raw.map(businessMap).toList(), seen = <String>{};
  for (final value in movements) {
    if (!_id.hasMatch('${value['id']}') ||
        !seen.add(value['id']) ||
        !['receive', 'issue', 'return', 'transfer'].contains(value['kind']) ||
        value['sequence_number'] is! int ||
        value['sequence_number'] < 1)
      _fail('Die Lagerbewegungen sind nicht eindeutig belegt.');
    materialReturnQuantity(value['quantity']);
  }
  final result = <Map<String, dynamic>>[];
  for (final issue in movements.where((v) => v['kind'] == 'issue')) {
    if (!_id.hasMatch('${issue['article_id']}') ||
        !_id.hasMatch('${issue['project_id']}') ||
        !_id.hasMatch('${issue['from_location_id']}') ||
        issue['to_location_id'] != null ||
        issue['reversal_of'] != null ||
        projectId != null && issue['project_id'] != projectId)
      _fail('Die Originalentnahme gehört nicht zum gewählten Projekt.');
    final original = materialReturnQuantity(issue['quantity']);
    var returned = BigInt.zero;
    for (final value in movements.where(
      (v) => v['reversal_of'] == issue['id'],
    )) {
      if (value['kind'] != 'return' ||
          value['article_id'] != issue['article_id'] ||
          value['project_id'] != issue['project_id'] ||
          value['from_location_id'] != null ||
          !_id.hasMatch('${value['to_location_id']}'))
        _fail('Eine Rückgabe widerspricht ihrer ursprünglichen Entnahme.');
      returned += materialReturnQuantity(value['quantity']);
    }
    if (returned > original)
      _fail('Die bisherigen Rückgaben übersteigen die Entnahme.');
    result.add({
      'issue': _copy(issue),
      'returned_quantity': materialReturnQuantityText(returned),
      'remaining_quantity': materialReturnQuantityText(original - returned),
    });
  }
  if (movements.any(
    (v) =>
        v['kind'] == 'return' &&
        !result.any((r) => r['issue']['id'] == v['reversal_of']),
  ))
    _fail(
      'Die Originalentnahme einer Rückgabe fehlt im gelesenen Lagerjournal.',
    );
  return result;
}

Map<String, dynamic> materialReturnReceipt(
  dynamic raw,
  Map<String, dynamic> body, {
  String? actorId,
}) {
  final value = businessMap(raw);
  if (!_id.hasMatch('${value['id']}') ||
      value['kind'] != 'return' ||
      value['article_id'] != body['article_id'] ||
      value['project_id'] != body['project_id'] ||
      value['reversal_of'] != body['reversal_of'] ||
      value['from_location_id'] != null ||
      value['to_location_id'] != body['to_location_id'] ||
      value['note'] != body['note'] ||
      !_id.hasMatch('${value['created_by']}') ||
      actorId != null && value['created_by'] != actorId ||
      value['created_at'] is! String ||
      DateTime.tryParse(value['created_at']) == null ||
      value['sequence_number'] is! int ||
      value['sequence_number'] < 1 ||
      materialReturnQuantity(value['quantity']) !=
          materialReturnQuantity(body['quantity']))
    _fail('Die Bestätigung entspricht nicht der ursprünglichen Rückgabe.', 0);
  return value;
}

dynamic _ordered(dynamic value) => value is Map
    ? {
        for (final key in value.keys.cast<String>().toList()..sort())
          key: _ordered(value[key]),
      }
    : value is List
    ? value.map(_ordered).toList()
    : value;

bool _sharedFieldsMatch(dynamic first, dynamic second) {
  if (first is Map && second is Map) {
    return first.keys
        .where(second.containsKey)
        .every((key) => _sharedFieldsMatch(first[key], second[key]));
  }
  if (first is List && second is List) {
    return first.length == second.length &&
        List.generate(
          first.length,
          (i) => i,
        ).every((i) => _sharedFieldsMatch(first[i], second[i]));
  }
  return jsonEncode(first) == jsonEncode(second);
}

Map<String, dynamic> _operationalReceipt(Map<String, dynamic> value) => {
  for (final entry in value.entries)
    if (!['unit_cost_net', 'cost_net'].contains(entry.key))
      entry.key: entry.key != 'article_snapshot'
          ? entry.value
          : {
              for (final key in [
                'id',
                'revision',
                'code',
                'name',
                'kind',
                'unit',
                'active',
                'price_policy',
              ])
                if (businessMap(entry.value).containsKey(key))
                  key: entry.value[key],
            },
};

/// The complete original is encrypted before any POST on bound online servers.
class MaterialReturnFlow extends ChangeNotifier {
  MaterialReturnFlow(this.session) {
    session.addListener(_changed);
  }
  static final _sessions = Expando<MaterialReturnFlow>();
  static MaterialReturnFlow forSession(BusinessSession session) =>
      _sessions[session] ??= MaterialReturnFlow(session);
  final BusinessSession session;
  Map<String, dynamic>? _pending;
  OnlineCommandJournalSession? _journal;
  bool _disposed = false;
  Map<String, dynamic> _original(Object? raw) {
    final value = businessMap(raw), body = businessMap(value['body']);
    if (value.length != 2 ||
        !value.containsKey('actor_id') ||
        !_id.hasMatch('${value['actor_id']}') ||
        body.length != 8 ||
        ![
          'kind',
          'article_id',
          'project_id',
          'reversal_of',
          'to_location_id',
          'quantity',
          'note',
          'request_id',
        ].every(body.containsKey) ||
        body['kind'] != 'return' ||
        [
          'article_id',
          'project_id',
          'reversal_of',
          'to_location_id',
          'request_id',
        ].any((key) => !_id.hasMatch('${body[key]}')) ||
        session.projectId != null && body['project_id'] != session.projectId ||
        body['note'] is! String ||
        body['note'].runes.length > 2000 ||
        RegExp(r'[\x00-\x08\x0b-\x1f]').hasMatch(body['note'])) {
      _fail('Der geschützte Rückgabeauftrag ist nicht unverändert lesbar.', 0);
    }
    materialReturnQuantity(body['quantity']);
    return _copy(value);
  }

  Map<String, dynamic> _saved(Map<String, dynamic> value) =>
      _original({'actor_id': value['actor_id'], 'body': value['body']});

  Future<void> restorePending() async {
    final context = contextKey;
    final actor = await _fresh(context);
    final journal = await session.openOnlineCommandJournal(
      actorId: actor,
      slot: 'material-return:${session.projectId ?? 'global'}',
      validate: _original,
      requireCurrent: () => _check(context),
    );
    _check(context);
    final saved = journal?.pending;
    if (saved != null && saved['actor_id'] != actor)
      _fail('Der Originalauftrag gehört zu einer anderen Anmeldung.', 403);
    _journal = journal;
    if (saved != null) {
      try {
        // A global warehouse grant alone is not access to the old project.
        // This endpoint checks current project rights before the saved note
        // enters the visible command controller.
        final body = businessMap(saved['body']);
        final issue = businessMap(
          await session.read('/inventory/movements/${body['reversal_of']}'),
        );
        _check(context);
        if (issue['id'] != body['reversal_of'] ||
            issue['kind'] != 'issue' ||
            issue['project_id'] != body['project_id'] ||
            issue['article_id'] != body['article_id']) {
          _fail(
            'Der Projektbezug des Originalauftrags konnte nicht bestätigt werden.',
            0,
          );
        }
      } catch (_) {
        _pending = null;
        notifyListeners();
        rethrow;
      }
      _pending = {...saved, 'context': context, 'token': session.api.token};
      notifyListeners();
    } else if (journal != null && _pending != null) {
      // Another authorized window may already have resolved the same original.
      // An absent journal on an old server does not establish that fact.
      _pending = null;
      notifyListeners();
    }
  }

  bool busy = false;
  String get contextKey => jsonEncode([
    session.api.base,
    session.api.version,
    session.api.token,
    session.projectId,
    session.projectCreationScope,
  ]);
  bool get readable =>
      !_disposed &&
      session.allowed &&
      session.hasModule('inventory') &&
      session.can('inventory.read');
  bool get writable =>
      readable &&
      session.canWrite('inventory.write') &&
      session.sectionEnabled('material');
  Map<String, dynamic>? get pending =>
      readable && _pending?['context'] == contextKey
      ? _copy(_pending!['body'])
      : null;
  void _changed() {
    if (_pending != null && _pending!['token'] != session.api.token)
      _pending = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    session.removeListener(_changed);
    _pending?.clear();
    _pending = null;
    _journal = null;
    super.dispose();
  }

  void _check(String context, {bool write = false}) {
    if (context != contextKey || !(write ? writable : readable))
      _fail('Die aktuelle Material- oder Projektberechtigung fehlt.', 403);
  }

  Future<String> _fresh(String context, {bool write = false}) async {
    if (context != contextKey || session.api.token == null)
      _fail('Die ursprüngliche Anmeldung ist nicht mehr verfügbar.', 403);
    await session.load();
    _check(context, write: write);
    if (session.error != null)
      _fail('Die aktuellen Materialrechte konnten nicht geprüft werden.', 0);
    final actor = businessMap(await session.api.call('/api/me'));
    _check(context, write: write);
    if (!_id.hasMatch('${actor['id']}'))
      _fail('Die aktuelle Anmeldung ist nicht eindeutig.', 403);
    return actor['id'];
  }

  Future<Map<String, dynamic>> sources() async {
    final context = contextKey;
    final actor = await _fresh(context, write: true);
    final results = await Future.wait([
      session.read(session.query('/inventory/movements')),
      session.read('/inventory/locations'),
    ]);
    _check(context, write: true);
    final locations = businessItems(results[1]);
    if (locations.any(
      (v) =>
          !_id.hasMatch('${v['id']}') ||
          v['active'] is! bool ||
          v['name'] is! String,
    ))
      _fail('Die Ziellager sind nicht eindeutig belegt.');
    return {
      'actor_id': actor,
      'context': context,
      'options': materialReturnOptions(
        businessMap(results[0])['items'],
        projectId: session.projectId,
      ),
      'locations': locations.where((v) => v['active'] == true).toList(),
    };
  }

  Future<Map<String, dynamic>> submit(
    Map<String, dynamic> original,
    String quantity,
    String destination,
    String note,
  ) async {
    if (busy || _pending != null)
      _fail('Zuerst den ursprünglichen Rückgabeauftrag prüfen.', 409);
    busy = true;
    notifyListeners();
    try {
      final amount = materialReturnQuantity(
        quantity.trim().replaceAll(',', '.'),
      );
      if (note.runes.length > 2000 ||
          RegExp(r'[\x00-\x08\x0b-\x1f]').hasMatch(note))
        _fail('Die Buchungsnotiz ist zu lang oder enthält ungültige Zeichen.');
      final data = await sources();
      await restorePending();
      if (_pending != null)
        _fail(
          'Zuerst die Bestätigung der ursprünglichen Rückgabe klären.',
          409,
        );
      final option = businessItems(data['options'])
          .where((v) => v['issue']['id'] == original['id'])
          .firstOrNull;
      if (option == null ||
          jsonEncode(_issueIdentity(option['issue'])) !=
              jsonEncode(_issueIdentity(original)))
        _fail(
          'Die Originalentnahme ist nicht mehr unverändert verfügbar.',
          409,
        );
      if (BigInt.parse(
            (option['remaining_quantity'] as String).replaceAll('.', ''),
          ) <
          amount)
        _fail(
          'Die Rückgabe übersteigt die noch nicht zurückgegebene Menge.',
          409,
        );
      if (!businessItems(data['locations']).any((v) => v['id'] == destination))
        _fail('Ein aktuelles aktives Ziellager auswählen.');
      final next = {
        'context': data['context'],
        'token': session.api.token,
        'actor_id': data['actor_id'],
        'body': {
          'kind': 'return',
          'article_id': original['article_id'],
          'project_id': original['project_id'],
          'reversal_of': original['id'],
          'to_location_id': destination,
          'quantity': materialReturnQuantityText(amount),
          'note': note.trim(),
          'request_id': offlineId(),
        },
      };
      await _journal?.prepare(_saved(next));
      _check(data['context'], write: true);
      _pending = next;
      return await _send();
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> retry() async {
    if (busy || _pending == null)
      _fail('Kein unbestätigter Rückgabeauftrag verfügbar.', 409);
    busy = true;
    notifyListeners();
    try {
      return await _send();
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> _send() async {
    final original = _pending!;
    final actor = await _fresh(original['context'], write: true);
    if (!identical(original, _pending) || actor != original['actor_id'])
      _fail(
        'Der ursprüngliche Auftrag gehört zu einer anderen Anmeldung.',
        403,
      );
    await _journal?.requireOriginal(_saved(original));
    _check(original['context'], write: true);
    late dynamic response;
    try {
      response = await session.api.call(
        session.path('/inventory/movements'),
        _copy(original['body']),
      );
    } on ApiException catch (error) {
      if (error.status == 409 && error.requestResolution == 'not_accepted') {
        _check(original['context'], write: true);
        await _journal?.clear(_saved(original));
        _check(original['context'], write: true);
        if (identical(original, _pending)) {
          _pending = null;
          notifyListeners();
        }
      }
      rethrow;
    }
    _check(original['context'], write: true);
    if (!identical(original, _pending))
      _fail('Die Materialansicht wurde gewechselt.', 0);
    final result = materialReturnReceipt(
      response,
      original['body'],
      actorId: original['actor_id'],
    );
    final stored = materialReturnReceipt(
      await session.read('/inventory/movements/${result['id']}'),
      original['body'],
      actorId: original['actor_id'],
    );
    _check(original['context'], write: true);
    if (!identical(original, _pending) ||
        stored['id'] != result['id'] ||
        jsonEncode(_ordered(_operationalReceipt(stored))) !=
            jsonEncode(_ordered(_operationalReceipt(result))) ||
        !_sharedFieldsMatch(stored, result))
      _fail(
        'Die Rückgabe konnte nicht eindeutig im Lagerjournal bestätigt werden.',
        0,
      );
    await _journal?.clear(_saved(original));
    _check(original['context'], write: true);
    _pending = null;
    notifyListeners();
    return result;
  }
}

class MaterialReturnDialog extends StatefulWidget {
  const MaterialReturnDialog({super.key, required this.flow});
  final MaterialReturnFlow flow;
  @override
  State<MaterialReturnDialog> createState() => _MaterialReturnDialogState();
}

class _MaterialReturnDialogState extends State<MaterialReturnDialog> {
  final form = GlobalKey<FormState>(),
      quantity = TextEditingController(),
      note = TextEditingController();
  List<Map<String, dynamic>> options = [], locations = [];
  String? issueId, destination, error;
  late final String opening = widget.flow.contextKey;
  bool loading = true;
  bool opened = false;
  bool confirmed = false;
  MaterialReturnFlow get flow => widget.flow;
  bool get visible => opening == flow.contextKey && flow.readable;
  @override
  void initState() {
    super.initState();
    flow.addListener(_changed);
    _load();
  }

  void _changed() {
    if (!mounted) return;
    if (!visible) {
      options = [];
      locations = [];
      quantity.clear();
      note.clear();
      confirmed = false;
    }
    setState(() {});
  }

  Future<void> _load() async {
    try {
      await flow.restorePending();
      if (flow.pending == null) {
        final data = await flow.sources();
        if (!mounted || !visible) return;
        options = businessItems(data['options'])
            .where((v) => v['remaining_quantity'] != '0.0000')
            .toList();
        locations = businessItems(data['locations']);
      }
      if (mounted && visible) opened = true;
    } catch (e) {
      if (mounted && visible) error = '$e';
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  void dispose() {
    flow.removeListener(_changed);
    quantity.dispose();
    note.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!visible || !flow.writable || flow.busy) return;
    try {
      setState(() => error = null);
      if (flow.pending != null) {
        await flow.retry();
      } else {
        if (!confirmed)
          _fail('Die tatsächliche Materialrückgabe ausdrücklich bestätigen.');
        if (!(form.currentState?.validate() ?? false)) return;
        final selected = options.firstWhere((v) => v['issue']['id'] == issueId);
        await flow.submit(
          selected['issue'],
          quantity.text,
          destination!,
          note.text,
        );
      }
      if (mounted && visible) Navigator.pop(context, true);
    } catch (e) {
      if (mounted && visible) setState(() => error = '$e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final pending = opened ? flow.pending : null;
    final selected = options
        .where((v) => v['issue']['id'] == issueId)
        .firstOrNull;
    return AlertDialog(
      title: const Text('Material zurückgeben'),
      content: SizedBox(
        width: 520,
        child: !visible
            ? const Text('Die Materialansicht ist nicht mehr freigegeben.')
            : SingleChildScrollView(
                child: Form(
                  key: form,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (loading) const LinearProgressIndicator(),
                      if (error != null) Notice(error!, error: true),
                      if (pending != null) ...[
                        const Notice(
                          'Die Bestätigung ist noch offen. Erneut wird ausschließlich die ursprüngliche Rückgabe geprüft.',
                        ),
                        Text('Menge: ${pending['quantity']}'),
                        if (pending['note'] != '') Text(pending['note']),
                      ] else if (!loading && opened) ...[
                        DropdownButtonFormField<String>(
                          initialValue: issueId,
                          isExpanded: true,
                          decoration: const InputDecoration(
                            labelText: 'Originalentnahme',
                          ),
                          items: [
                            for (final value in options)
                              DropdownMenuItem(
                                value: value['issue']['id'],
                                child: Text(
                                  '${value['issue']['article_snapshot']?['name'] ?? value['issue']['article_id']} · Rest ${value['remaining_quantity']}',
                                ),
                              ),
                          ],
                          onChanged: flow.busy
                              ? null
                              : (value) => setState(() {
                                  issueId = value;
                                  quantity.clear();
                                  confirmed = false;
                                }),
                          validator: (v) =>
                              v == null ? 'Originalentnahme auswählen.' : null,
                        ),
                        if (selected != null) ...[
                          ListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text(
                              '${selected['issue']['article_snapshot']?['name'] ?? selected['issue']['article_id']}',
                            ),
                            subtitle: Text(
                              'Projekt: ${flow.session.projects.where((p) => p['id'] == selected['issue']['project_id']).firstOrNull?['name'] ?? selected['issue']['project_id']}\nNoch nicht zurückgegeben: ${selected['remaining_quantity']}',
                            ),
                          ),
                        ],
                        DropdownButtonFormField<String>(
                          initialValue: destination,
                          isExpanded: true,
                          decoration: const InputDecoration(
                            labelText: 'Ziellager',
                          ),
                          items: [
                            for (final value in locations)
                              DropdownMenuItem(
                                value: value['id'],
                                child: Text(value['name']),
                              ),
                          ],
                          onChanged: flow.busy
                              ? null
                              : (v) => setState(() => destination = v),
                          validator: (v) =>
                              v == null ? 'Ziellager auswählen.' : null,
                        ),
                        TextFormField(
                          key: const ValueKey('material-return-quantity'),
                          controller: quantity,
                          enabled: !flow.busy,
                          decoration: const InputDecoration(
                            labelText: 'Rückgabemenge',
                          ),
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                          validator: (v) => v == null || v.trim().isEmpty
                              ? 'Menge angeben.'
                              : null,
                        ),
                        TextFormField(
                          key: const ValueKey('material-return-note'),
                          controller: note,
                          enabled: !flow.busy,
                          maxLines: 3,
                          decoration: const InputDecoration(
                            labelText: 'Buchungsnotiz',
                          ),
                        ),
                        const Notice(
                          'Artikel und Projekt bleiben an die Originalentnahme gebunden. Die Rückgabe übernimmt deren historischen Einstandspreis.',
                        ),
                        CheckboxListTile(
                          contentPadding: EdgeInsets.zero,
                          value: confirmed,
                          onChanged: flow.busy
                              ? null
                              : (value) =>
                                    setState(() => confirmed = value == true),
                          title: const Text(
                            'Ich bestätige die tatsächliche Materialrückgabe zur ausgewählten Originalentnahme.',
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Schließen'),
        ),
        FilledButton(
          onPressed:
              visible &&
                  flow.writable &&
                  !loading &&
                  !flow.busy &&
                  (pending != null || confirmed)
              ? _save
              : null,
          child: Text(
            pending == null
                ? 'Rückgabe buchen'
                : 'Ursprüngliche Rückgabe erneut prüfen',
          ),
        ),
      ],
    );
  }
}

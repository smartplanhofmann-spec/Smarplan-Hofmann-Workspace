import 'dart:convert';

import 'api.dart';
import 'business_session.dart' show businessMap, businessItems;

const mileageRoot = '/personnel/travel/mileage';
const mileageFeature = 'travel_private_car_mileage';
const mileageReadFeature = 'travel_private_car_mileage_read';
const mileageRule = 'de_travel_2026_v4_private_car';
const mileageDeclarations = {
  'employee_bears_vehicle_costs': 'Ich trage die Fahrzeugkosten selbst.',
  'no_employer_vehicle': 'Es wurde kein Fahrzeug vom Arbeitgeber gestellt.',
  'only_business_travel': 'Die Fahrt war ausschließlich dienstlich.',
  'no_commuting_or_family_home': 'Keine Pendel- oder Familienheimfahrt.',
  'no_collection_point_or_wide_area':
      'Kein Sammelpunkt oder weiträumiges Tätigkeitsgebiet.',
  'no_other_reimbursement': 'Keine anderweitige Erstattung dieser Fahrt.',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message) => throw ApiException(400, message);
dynamic _ordered(dynamic v) => v is Map
    ? {
        for (final key in v.keys.cast<String>().toList()..sort())
          key: _ordered(v[key]),
      }
    : v is List
    ? v.map(_ordered).toList()
    : v;
bool _same(dynamic a, dynamic b) =>
    jsonEncode(_ordered(a)) == jsonEncode(_ordered(b));
String _text(dynamic value, int max) {
  if (value is! String ||
      value.trim().isEmpty ||
      value.runes.length > max ||
      RegExp(r'[\x00-\x08\x0b-\x1f]').hasMatch(value))
    _fail(
      'Die belegten Fahrtangaben vollständig und ohne unzulässige Zeichen angeben.',
    );
  return value.trim();
}

int mileageMetres(dynamic value) {
  if (value is! int || value < 1 || value > 2000000)
    _fail(
      'Jede tatsächliche Teilstrecke benötigt 1 bis 2.000.000 ganze Meter.',
    );
  return value;
}

Map<String, dynamic> mileageRef(dynamic raw) {
  final v = businessMap(raw);
  if (!_id.hasMatch('${v['id']}') ||
      v['revision'] is! int ||
      v['revision'] < 1 ||
      !_hash.hasMatch('${v['content_hash']}'))
    _fail('Die gebundene Originalfassung fehlt.');
  return {
    for (final key in ['id', 'revision', 'content_hash']) key: v[key],
  };
}

DateTime _instant(dynamic value) {
  if (value is! String ||
      !RegExp(r'^2026-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+0[12]:00$')
          .hasMatch(value))
    _fail('Tatsächliche Ortszeit 2026 mit belegter Berliner Zeitlage angeben.');
  final parsed = DateTime.tryParse(value);
  if (parsed == null) _fail('Die tatsächliche Fahrtzeit ist ungültig.');
  final civil = DateTime.tryParse(value.substring(0, 19));
  if (civil == null ||
      civil.toIso8601String().substring(0, 19) != value.substring(0, 19))
    _fail('Die tatsächliche lokale Fahrtzeit existiert nicht.');
  return parsed;
}

Map<String, dynamic> mileageCatalog(dynamic raw) {
  final v = businessMap(raw), rate = businessMap(v['rate']);
  if (v['schema_version'] is! int ||
      v['schema_version'] != 1 ||
      v['feature'] != mileageFeature ||
      v['rule_version'] != mileageRule ||
      !_hash.hasMatch('${v['rule_hash']}') ||
      !_hash.hasMatch('${v['table_hash']}') ||
      v['scope'] != 'employee_domestic_private_car_one_day_round_trip' ||
      v['max_legs'] is! int ||
      v['max_legs'] != 100 ||
      v['max_leg_distance_m'] is! int ||
      v['max_leg_distance_m'] != 2000000 ||
      v['rounding'] != 'half_up_once_on_total_metres' ||
      v['payroll_supported'] != false ||
      v['automatic_payment'] != false ||
      rate['vehicle_kind'] != 'private_car' ||
      rate['country'] != 'Deutschland' ||
      rate['rate_minor_per_km'] is! int ||
      rate['rate_minor_per_km'] != 30 ||
      rate['metres_per_km'] is! int ||
      rate['metres_per_km'] != 1000 ||
      rate['effective_from'] != '2026-01-01' ||
      rate['effective_to'] != '2026-12-31')
    _fail(
      'Der Server unterstützt diesen ausdrücklichen Kilometervertrag nicht.',
    );
  return v;
}

Map<String, dynamic> mileageDetails(
  dynamic raw,
  String employee,
  Map<String, dynamic> sources,
) {
  final v = businessMap(raw), m = businessMap(v['mileage']);
  const fields = {
    'purpose',
    'project_id',
    'departed_at',
    'returned_at',
    'timezone',
    'home_site_ref',
    'first_workplace_ref',
    'source_file_ids',
    'mileage',
  };
  final mileageFields = {
    'schema_version',
    'vehicle_kind',
    'vehicle_registration',
    'vehicle_file_id',
    'declaration_file_id',
    'legs',
    'review_note',
    ...mileageDeclarations.keys,
  };
  if (v.keys.toSet().difference(fields).isNotEmpty ||
      fields.difference(v.keys.toSet()).isNotEmpty ||
      m.keys.toSet().difference(mileageFields).isNotEmpty ||
      mileageFields.difference(m.keys.toSet()).isNotEmpty ||
      v['timezone'] != 'Europe/Berlin' ||
      m['schema_version'] is! int ||
      m['schema_version'] != 1 ||
      m['vehicle_kind'] != 'private_car' ||
      mileageDeclarations.keys.any((key) => m[key] is! bool) ||
      m['legs'] is! List ||
      m['legs'].isEmpty ||
      m['legs'].length > 100)
    _fail('Die Fahrt benötigt den eigenen vollständigen privaten Pkw-Vertrag.');
  _text(v['purpose'], 1000);
  _text(m['vehicle_registration'], 32);
  _text(m['review_note'], 2000);
  final start = _instant(v['departed_at']), end = _instant(v['returned_at']);
  final day = v['departed_at'].substring(0, 10);
  if (!start.isBefore(end) || v['returned_at'].substring(0, 10) != day)
    _fail(
      'Die abgeschlossene Rundfahrt muss an genau einem Kalendertag liegen.',
    );
  final files = businessItems(sources['files']),
      sites = businessItems(sources['sites']);
  final ids = v['source_file_ids'];
  if (ids is! List ||
      ids.isEmpty ||
      ids.length > 100 ||
      ids.toSet().length != ids.length ||
      ids.any(
        (id) => !files.any(
          (f) =>
              f['id'] == id &&
              f['employee_id'] == employee &&
              f['purpose'] == 'personnel',
        ),
      ))
    _fail('Die persönlichen Fahrtoriginale ausdrücklich auswählen.');
  void evidence(dynamic id) {
    if (!ids.contains(id))
      _fail(
        'Fahrzeug-, Erklärungs- und Streckenbelege am Fahrtoriginal binden.',
      );
  }

  Map<String, dynamic> site(dynamic ref, [String? kind]) {
    final exact = mileageRef(ref);
    final matches = sites.where((s) => _same(mileageRef(s), exact));
    if (matches.length != 1 || matches.single['employee_id'] != employee)
      _fail(
        'Eine Stättenfassung gehört nicht zu den ursprünglichen Personennachweisen.',
      );
    final value = matches.single, d = businessMap(value['details']);
    if (value['status'] != 'active' ||
        d['timezone'] != 'Europe/Berlin' ||
        d['rate_id'] != 'de_2026' ||
        d['effective_from'].compareTo(day) > 0 ||
        d['effective_to'] != null && d['effective_to'].compareTo(day) < 0 ||
        kind != null && d['kind'] != kind)
      _fail('Eine Stätte ist nicht für diesen inländischen Fahrttag belegt.');
    return value;
  }

  site(v['home_site_ref'], 'home');
  if (v['first_workplace_ref'] != null)
    site(v['first_workplace_ref'], 'first_workplace');
  evidence(m['vehicle_file_id']);
  evidence(m['declaration_file_id']);
  final seen = <String>{};
  Map<String, dynamic>? previous;
  final legs = businessItems(m['legs']);
  for (final leg in legs) {
    if (!_same(
          leg.keys.toList()..sort(),
          [
            'id',
            'departed_at',
            'arrived_at',
            'from_site_ref',
            'to_site_ref',
            'distance_m',
            'evidence_file_id',
          ]..sort(),
        ) ||
        !_id.hasMatch('${leg['id']}') ||
        !seen.add(leg['id']))
      _fail('Jede Teilstrecke benötigt ihre eindeutige ursprüngliche Fassung.');
    mileageMetres(leg['distance_m']);
    evidence(leg['evidence_file_id']);
    final from = site(leg['from_site_ref']), to = site(leg['to_site_ref']);
    final depart = _instant(leg['departed_at']),
        arrive = _instant(leg['arrived_at']);
    if (!depart.isBefore(arrive) ||
        leg['departed_at'].substring(0, 10) != day ||
        leg['arrived_at'].substring(0, 10) != day ||
        depart.isBefore(start) ||
        arrive.isAfter(end) ||
        previous != null &&
            (!_same(previous['to_site_ref'], leg['from_site_ref']) ||
                depart.isBefore(_instant(previous['arrived_at']))) ||
        from['id'] == to['id'] ||
        ![
          from['details']['kind'],
          to['details']['kind'],
        ].contains('external_fixed'))
      _fail(
        'Die belegten Strecken müssen eine zusammenhängende dienstliche Orts- und Zeitfolge bilden.',
      );
    previous = leg;
  }
  final base = legs.first['from_site_ref'];
  if (!_same(base, legs.last['to_site_ref']) ||
      ![
        _same(base, v['home_site_ref']),
        _same(base, v['first_workplace_ref']),
      ].contains(true) ||
      legs.first['departed_at'] != v['departed_at'] ||
      legs.last['arrived_at'] != v['returned_at'])
    _fail(
      'Die Rundfahrt muss vollständig an derselben Wohnung oder ersten Tätigkeitsstätte beginnen und enden.',
    );
  for (final leg in legs) {
    for (final ref in [leg['from_site_ref'], leg['to_site_ref']]) {
      if (!_same(ref, base) && site(ref)['details']['kind'] != 'external_fixed')
        _fail(
          'Zwischenpunkte müssen ausschließlich auswärtige feste Stätten sein.',
        );
    }
  }
  return v;
}

Map<String, dynamic> mileageTrip(dynamic raw, String employee) {
  final v = businessMap(raw);
  mileageRef(v);
  if (v['schema_version'] is! int ||
      v['schema_version'] != 1 ||
      v['employee_id'] != employee ||
      v['kind'] != 'trip' ||
      v['rule_version'] != mileageRule ||
      !['draft', 'submitted', 'rejected'].contains(v['status']))
    _fail('Das Original gehört nicht zu dieser Kilometerfahrt.');
  mileageDetails(v['details'], employee, businessMap(v['sources']));
  return v;
}

Map<String, dynamic> mileageCalculation(
  dynamic raw,
  List<Map<String, dynamic>> refs, {
  Map<String, dynamic>? trip,
}) {
  final v = businessMap(raw), totals = businessMap(v['totals']);
  if (v['rule_version'] != mileageRule ||
      !_hash.hasMatch('${v['rule_hash']}') ||
      !_hash.hasMatch('${v['table_hash']}') ||
      v['payroll_required'] != false ||
      v['can_approve'] is! bool ||
      v['can_pay'] is! bool ||
      v['blockers'] is! List ||
      v['mileage_items'] is! List ||
      v['days'] is! List ||
      v['days'].length != 1 ||
      refs.length != 1 ||
      [
        'expense_items',
        'transport_sources',
        'ground_calendar_sources',
        'mixed_program_sources',
      ].any((key) => v[key] is! List || v[key].isNotEmpty))
    _fail(
      'Die Kilometerberechnung ist nicht an den eigenen engen Vertrag gebunden.',
    );
  var metres = 0;
  final ids = <String>{};
  final lines = businessItems(v['mileage_items']);
  if (lines.isEmpty || lines.length > 100)
    _fail('Die vollständigen belegten Teilstrecken fehlen.');
  for (final line in lines) {
    if (!_same(
          line.keys.toList()..sort(),
          [
            'trip_ref',
            'leg_id',
            'from_site_ref',
            'to_site_ref',
            'distance_m',
            'rate_minor_per_km',
            'evidence_file_id',
            'evidence_sha256',
          ]..sort(),
        ) ||
        !_same(mileageRef(line['trip_ref']), refs.single) ||
        !_id.hasMatch('${line['leg_id']}') ||
        !ids.add(line['leg_id']) ||
        line['rate_minor_per_km'] is! int ||
        line['rate_minor_per_km'] != 30 ||
        !_id.hasMatch('${line['evidence_file_id']}') ||
        !_hash.hasMatch('${line['evidence_sha256']}'))
      _fail('Ein Streckennachweis gehört nicht zur ursprünglichen Fahrt.');
    mileageRef(line['from_site_ref']);
    mileageRef(line['to_site_ref']);
    metres += mileageMetres(line['distance_m']);
  }
  final amount = (metres * 30 + 500) ~/ 1000, day = businessMap(v['days'][0]);
  final paid = totals['already_paid_minor'];
  if (paid is! int ||
      paid < 0 ||
      paid > 1000000000000 ||
      totals.values.any((value) => value is! int || value < 0) ||
      totals['mileage_distance_m'] != metres ||
      totals['mileage_allowance_minor'] != amount ||
      totals['requested_minor'] != amount ||
      totals['tax_free_minor'] != amount ||
      [
        'meal_base_minor',
        'meal_reduction_minor',
        'meal_allowance_minor',
        'lodging_allowance_minor',
        'expense_allowance_minor',
        'expense_already_paid_minor',
        'flat_taxable_minor',
        'individual_taxable_minor',
        'benefit_in_kind_minor',
      ].any((key) => totals[key] != 0) ||
      totals['remaining_minor'] != (amount > paid ? amount - paid : 0) ||
      totals['overpaid_minor'] != (paid > amount ? paid - amount : 0) ||
      v['can_approve'] != v['blockers'].isEmpty ||
      v['can_pay'] != (v['blockers'].isEmpty && amount > paid) ||
      day['country'] != 'Deutschland' ||
      day['letter_m'] != false ||
      day['mileage_allowance_minor'] != amount ||
      [
        'base_minor',
        'meal_reduction_minor',
        'meal_allowance_minor',
        'lodging_allowance_minor',
        'benefit_in_kind_minor',
      ].any((key) => day[key] != 0))
    _fail(
      'Kilometer, einmalige Gesamtrundung und tatsächlicher Erstattungsstand widersprechen sich.',
    );
  if (trip != null) {
    mileageTrip(trip, trip['employee_id']);
    for (final key in mileageDeclarations.keys) {
      final missing = trip['details']['mileage'][key] == false;
      final blockers = businessItems(v['blockers'])
          .where((b) => b['code'] == 'mileage_${key}_missing')
          .toList();
      if (missing != blockers.isNotEmpty ||
          blockers.any((b) => !_same(b['source_ref'], refs.single)))
        _fail(
          'Eine fehlende persönliche Erklärung darf die Abrechnung nicht freigeben.',
        );
    }
    final legs = businessItems(trip['details']['mileage']['legs']);
    if (!_same(mileageRef(trip), refs.single) ||
        lines.length != legs.length ||
        day['date'] != trip['details']['departed_at'].substring(0, 10))
      _fail(
        'Die Abrechnung enthält nicht die vollständige ursprüngliche Fahrt.',
      );
    for (var i = 0; i < legs.length; i++) {
      final leg = legs[i], line = lines[i];
      final files = businessItems(trip['sources']['files']);
      if (line['leg_id'] != leg['id'] ||
          line['distance_m'] != leg['distance_m'] ||
          !_same(line['from_site_ref'], leg['from_site_ref']) ||
          !_same(line['to_site_ref'], leg['to_site_ref']) ||
          line['evidence_file_id'] != leg['evidence_file_id'] ||
          !files.any(
            (f) =>
                f['id'] == line['evidence_file_id'] &&
                f['sha256'] == line['evidence_sha256'],
          ))
        _fail(
          'Ein ursprünglicher Strecken- oder Belegnachweis wurde verändert.',
        );
    }
  }
  return v;
}

Map<String, dynamic> mileagePreviewInput(
  Map<String, dynamic> trip,
  String note, {
  Map<String, dynamic>? previous,
}) {
  mileageTrip(trip, trip['employee_id']);
  final day = trip['details']['departed_at'].substring(0, 10);
  return {
    'employee_id': trip['employee_id'],
    'trip_refs': [mileageRef(trip)],
    'period_from': day,
    'period_to': day,
    'settlement_unit': 'trip',
    'tax_choice': 'tax_free_only',
    'requested_meal_minor': 0,
    'requested_lodging_minor': 0,
    'correction_of': previous == null ? null : mileageRef(previous),
    'review_note': _text(note, 2000),
  };
}

Map<String, dynamic> mileagePreview(
  dynamic raw,
  Map<String, dynamic> body,
  Map<String, dynamic> trip,
) {
  final v = businessMap(raw);
  if (v['employee_id'] != body['employee_id'] ||
      !_hash.hasMatch('${v['source_hash']}') ||
      !_hash.hasMatch('${v['preview_hash']}') ||
      [
        'trip_refs',
        'period_from',
        'period_to',
        'settlement_unit',
        'tax_choice',
        'requested_meal_minor',
        'requested_lodging_minor',
        'correction_of',
        'review_note',
      ].any((key) => !_same(v[key], body[key])))
    _fail(
      'Die Kilometervorschau gehört nicht zur ausdrücklich ausgewählten Fahrt.',
    );
  return mileageCalculation(v, businessItems(body['trip_refs']), trip: trip);
}

Map<String, dynamic> mileageResult(
  dynamic raw,
  Map<String, dynamic> body,
  String operation, {
  required String actorId,
  required String targetId,
}) {
  final value = businessMap(raw), kind = operation.split('.').first;
  mileageRef(value);
  if (value['schema_version'] is! int ||
      value['schema_version'] != 1 ||
      value['id'] != targetId ||
      value['employee_id'] != body['employee_id'] ||
      value['kind'] != kind ||
      value['created_by'] != actorId ||
      body['revision'] is! int ||
      value['revision'] != body['revision'] + 1)
    _fail(
      'Die Kilometerquittung gehört nicht zur ursprünglichen Person, Fassung und Handlung.',
    );
  if (kind == 'trip') {
    mileageTrip(value, body['employee_id']);
    if (operation == 'trip.save') {
      if (!_same(value['details'], body['details']) ||
          value['status'] != 'draft' ||
          value['correction_reason'] != body['correction_reason'])
        _fail('Die gespeicherte Fahrt ersetzt ursprüngliche Streckenangaben.');
    } else if (operation == 'trip.submit') {
      if (value['status'] != 'submitted' ||
          value['submitted_by'] != actorId ||
          body['confirmed'] != true)
        _fail(
          'Die Einreichung gehört nicht zur ausdrücklich bestätigten Fahrt.',
        );
    } else if (operation == 'trip.reject') {
      if (value['status'] != 'rejected' ||
          value['decision']?['by'] != actorId ||
          value['decision']?['reason'] != body['reason'] ||
          body['confirmed'] != true)
        _fail(
          'Die Zurückweisung entspricht nicht der ursprünglichen Entscheidung.',
        );
    } else {
      _fail('Unbekannte Kilometer-Fahrthandlung.');
    }
  } else if (kind == 'settlement') {
    final details = {
      for (final entry in body.entries)
        if (![
          'id',
          'request_id',
          'revision',
          'source_hash',
          'preview_hash',
          'confirmed',
        ].contains(entry.key))
          entry.key: entry.value,
    };
    if (operation != 'settlement.approve' ||
        value['status'] != 'approved' ||
        body['confirmed'] != true ||
        !_same(value['details'], details) ||
        value['source_hash'] != body['source_hash'] ||
        value['preview_hash'] != body['preview_hash'])
      _fail(
        'Die fremdgeprüfte Kilometerabrechnung entspricht nicht dem ursprünglichen Auftrag.',
      );
    final trips = businessItems(value['sources']?['trips']);
    if (trips.length != 1 ||
        trips.single['submitted_by'] == actorId ||
        value['sources']?['employee']?['user_id'] == actorId)
      _fail(
        'Die Kilometerabrechnung benötigt die ursprüngliche unabhängige Freigabe.',
      );
    mileageCalculation(
      value['calculation'],
      businessItems(details['trip_refs']),
      trip: trips.single,
    );
  } else if (kind == 'payment') {
    final details = {
      for (final entry in body.entries)
        if (![
          'employee_id',
          'id',
          'request_id',
          'revision',
          'source_hash',
          'confirmed',
        ].contains(entry.key))
          entry.key: entry.value,
    };
    final sources = businessMap(value['sources']),
        settlement = businessMap(sources['settlement']);
    if (operation != 'payment.record' ||
        body['confirmed'] != true ||
        !_same(value['details'], details) ||
        value['status'] != (body['action'] == 'void' ? 'void' : 'active') ||
        !_same(mileageRef(settlement), body['settlement_ref']) ||
        settlement['employee_id'] != body['employee_id'] ||
        settlement['calculation']?['rule_version'] != mileageRule ||
        sources['account']?['id'] != body['account_id'] ||
        sources['account']?['revision'] != body['account_revision'] ||
        !businessItems(sources['files']).any(
          (f) =>
              f['id'] == body['reference_file_id'] &&
              f['employee_id'] == body['employee_id'],
        ))
      _fail(
        'Der tatsächliche Geldfluss ersetzt ursprünglichen Betrag, Tag, Konto oder Abrechnungsfassung.',
      );
  } else {
    _fail('Unbekannte Kilometerquittung.');
  }
  return value;
}

import 'api.dart';
import 'business_session.dart';

const travelCashCategories = {
  'travel_allowance': 'Belegte Reisekostenerstattung',
};
final _id = RegExp(r'^[a-f0-9]{32}$'), _hash = RegExp(r'^[a-f0-9]{64}$');
Never _fail(String message) => throw ApiException(0, message);
bool _shape(dynamic value, Set<String> keys) =>
    value is Map && value.keys.every(keys.contains);
BigInt _cents(dynamic value) {
  if (value is! String ||
      !RegExp(r'^(?:0|[1-9]\d{0,12})\.\d{2}$').hasMatch(value))
    _fail('Genaue belegte EUR-Cents erwartet.');
  return BigInt.parse(value.replaceAll('.', ''));
}

bool _account(dynamic value) =>
    _shape(value, {
      'id',
      'code',
      'name',
      'kind',
      'currency',
      'active',
      'revision',
      'created_by',
      'created_at',
    }) &&
    _id.hasMatch('${value['id']}') &&
    value['currency'] == 'EUR' &&
    value['revision'] is int &&
    value['revision'] > 0;
bool _date(dynamic value) {
  if (value is! String || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value))
    return false;
  final parts = value.split('-').map(int.parse).toList();
  final parsed = DateTime.utc(parts[0], parts[1], parts[2]);
  return parsed.year == parts[0] &&
      parsed.month == parts[1] &&
      parsed.day == parts[2];
}

Map<String, dynamic> travelCashPublic(dynamic raw) {
  final source = businessMap(raw);
  if (!_shape(raw, {
        'kind',
        'id',
        'revision',
        'instance_id',
        'status',
        'date',
        'cash_movements',
        'source_path',
        'source_hash',
        'proof_hash',
      }) ||
      source['kind'] != 'travel_cash' ||
      !_id.hasMatch('${source['id']}') ||
      !_id.hasMatch('${source['instance_id']}') ||
      !_hash.hasMatch('${source['source_hash']}') ||
      !_hash.hasMatch('${source['proof_hash']}') ||
      source['revision'] is! int ||
      source['revision'] < 1 ||
      !['active', 'void'].contains(source['status']) ||
      !_date(source['date']) ||
      source['cash_movements'] is! List ||
      source['source_path'] !=
          '/personnel/travel/financial/${source['id']}?revision=${source['revision']}' ||
      (source['cash_movements'] as List).length !=
          (source['status'] == 'void' ? 0 : 1)) {
    _fail(
      'Die öffentliche Reisezahlungsquelle ist nicht eindeutig und datensparsam bestätigt.',
    );
  }
  for (final rawMovement in source['cash_movements']) {
    final movement = businessMap(rawMovement),
        categories = businessMap(businessMap(rawMovement)['categories']);
    if (!_shape(rawMovement, {
          'id',
          'date',
          'account',
          'direction',
          'amount',
          'categories',
        }) ||
        !_id.hasMatch('${movement['id']}') ||
        !_date(movement['date']) ||
        movement['date'] != source['date'] ||
        !_account(movement['account']) ||
        !['in', 'out'].contains(movement['direction']) ||
        !_shape(movement['categories'], {'travel_allowance'}) ||
        categories.length != 1 ||
        _cents(categories['travel_allowance']) <= BigInt.zero ||
        _cents(movement['amount']) != _cents(categories['travel_allowance'])) {
      _fail(
        'Der öffentliche Reisekostenbetrag ist nicht an tatsächlichen Tag, Geldkonto und Quelle gebunden.',
      );
    }
  }
  return source;
}

List<String> travelCashCategoryKeys(Map<String, dynamic> source) {
  travelCashPublic(source);
  return source['status'] == 'void' ? [] : ['travel_allowance'];
}

Map<String, dynamic> travelBankSource(dynamic raw) {
  final source = businessMap(raw);
  if (!_shape(raw, {
        'source_kind',
        'source_id',
        'account',
        'date',
        'direction',
        'amount',
        'source_path',
        'origin_hash',
        'source_hash',
      }) ||
      source['source_kind'] != 'travel_cash' ||
      !_id.hasMatch('${source['source_id']}') ||
      !_account(source['account']) ||
      !_date(source['date']) ||
      !['in', 'out'].contains(source['direction']) ||
      _cents(source['amount']) <= BigInt.zero ||
      !_hash.hasMatch('${source['origin_hash']}') ||
      !_hash.hasMatch('${source['source_hash']}') ||
      !RegExp(r'^/personnel/travel/financial/[a-f0-9]{32}\?revision=[1-9]\d*$')
          .hasMatch('${source['source_path']}')) {
    _fail(
      'Die Reisegeldquelle für den Bankabgleich enthält keinen vollständigen öffentlichen Nachweis.',
    );
  }
  return source;
}

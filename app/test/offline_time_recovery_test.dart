import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_binding.dart';
import 'package:smartplan_office/offline_time_recovery.dart';

final f = jsonDecode(
  File('test/fixtures/legacy_time_recovery.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));
final invalid = throwsA(
  isA<ApiException>().having(
    (e) => e.requestResolution,
    'no replacement command authority',
    isNull,
  ),
);
LegacyTimeOriginal original({
  Map<String, dynamic>? operation,
  Map<String, dynamic>? record,
}) => LegacyTimeOriginal.fromCache(
  operation ?? copy(f['retained_operation']),
  record ?? copy(f['cache_record']),
  accountId: f['account_id'],
);
void main() {
  test('actual independent Python event core hash, exact nonce envelope and bound original match without current timer values', () {
    final saved = original(),
        request = saved.query(nonce: f['lookup_command']['nonce']);
    expect(saved.preservedCore, f['expected_core']);
    expect(request, f['lookup_command']);
    expect(request.keys.toSet(), {
      'schema_version',
      'nonce',
      'kind',
      'project_id',
      'entry_id',
      'request_id',
      'request_hash',
    });
    expect(request.containsKey('body'), isFalse);
    expect(request.containsKey('employee_id'), isFalse);
    expect(request.containsKey('category_id'), isFalse);
    final result = saved.match(
      f['lookup_result'],
      request: request,
      binding: OfflineBinding.fromJson(f['binding']),
    );
    expect(result.action, 'stop');
    expect(result.occurredAt.microsecond, 789);
    expect(result.occurredAt.millisecond, 456);
  });
  test('captured old basis is immutable and a later server-profile substitution cannot change its hash', () {
    final record = copy(f['cache_record']),
        op = copy(f['retained_operation']),
        saved = original(operation: op, record: record),
        before = saved.requestHash;
    record['employee_id'] = 'f' * 32;
    record['category_id'] = 'e' * 32;
    op['body']['sequence'] = 99;
    expect(saved.requestHash, before);
    final view = saved.preservedCore;
    view['employee_id'] = 'd' * 32;
    expect(saved.requestHash, before);
  });
  test('unknown old employee or category basis never gets inferred from a new firm', () {
    for (final key in [
      'employee_id',
      'category_id',
      'user_id',
      'project_id',
      'id',
    ]) {
      final record = copy(f['cache_record'])..remove(key);
      expect(() => original(record: record), invalid);
    }
    final record = copy(f['cache_record'])..['employee_id'] = 'a' * 32 + '\n';
    expect(() => original(record: record), invalid);
  });
  test('positions, foreign fields, modified event IDs and noncanonical native dates are not silently hashed', () {
    for (final changes in [
      {
        'position': {'latitude': '50', 'longitude': '10'},
      },
      {'employee_id': 'a' * 32},
      {'category_id': null},
      {'event_id': 'a' * 32},
      {'sequence': 3},
      {'revision': true},
      {'occurred_at': '2026-02-30T09:00:00.000Z'},
      {'occurred_at': '2026-01-01T09:00:00Z'},
      {'occurred_at': '2026-01-01T09:00:00.000000Z'},
      {'occurred_at': '2026-01-01T10:00:00.000+01:00'},
    ]) {
      final op = copy(f['retained_operation']);
      op['body'].addAll(changes);
      expect(() => original(operation: op), invalid);
    }
  });
  test('Python timestamp projection retains exact seconds milliseconds and microseconds', () {
    for (final pair in [
      ['2026-11-03T09:00:00.000Z', '2026-11-03T09:00:00+00:00'],
      ['2026-11-03T09:00:00.123Z', '2026-11-03T09:00:00.123000+00:00'],
      ['2026-11-03T09:00:00.000001Z', '2026-11-03T09:00:00.000001+00:00'],
    ]) {
      final op = copy(f['retained_operation']);
      op['body']['occurred_at'] = pair[0];
      expect(original(operation: op).preservedCore['occurred_at'], pair[1]);
    }
  });
  test('wrong binding, nonce, actor, hashes or self-consistent changed original core never confirms', () {
    final saved = original(),
        request = copy(f['lookup_command']),
        binding = OfflineBinding.fromJson(f['binding']);
    for (final changes in [
      {'nonce': 'f' * 32},
      {'lookup_hash': 'f' * 64},
      {'request_id': 'f' * 32},
      {'entry_id': 'f' * 32},
      {'request_hash': 'f' * 64},
      {'schema_version': true},
      {'kind': 'plan_write'},
      {
        'binding': {...copy(f['binding']), 'instance_id': 'f' * 32},
      },
    ]) {
      final reply = copy(f['lookup_result'])..addAll(changes);
      expect(
        () => saved.match(reply, request: request, binding: binding),
        invalid,
      );
    }
    final wrong = copy(f['lookup_result']);
    wrong['original']['actor_id'] = 'e' * 32;
    expect(
      () => saved.match(wrong, request: request, binding: binding),
      invalid,
    );
    final altered = copy(f['lookup_result']);
    altered['original']['core']['employee_id'] = 'f' * 32;
    altered['original']['request_hash'] = offlineBindingHash(
      altered['original']['core'],
    );
    expect(
      () => saved.match(altered, request: request, binding: binding),
      invalid,
    );
    final numeric = copy(f['lookup_result']);
    numeric['original']['core']['sequence'] = 2.0;
    expect(
      () => saved.match(numeric, request: request, binding: binding),
      invalid,
    );
  });
}

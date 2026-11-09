import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/offline_binding.dart';

final fixture = jsonDecode(
  File('test/fixtures/offline_binding_v2.json').readAsStringSync(),
) as Map<String, dynamic>;
final account = fixture['account_id'] as String;
final binding = OfflineBinding.fromJson(
  fixture['context']['binding'],
  expectedAccountId: account,
);

Map<String, dynamic> copy(dynamic raw) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(raw)) as Map);

final invalid = throwsA(
  isA<ApiException>().having(
    (error) => error.requestResolution,
    'never authorizes a new send',
    isNull,
  ),
);

Map<String, dynamic> lookup({Map<String, dynamic>? command, String? planId}) {
  final request = fixture['lookup_command'];
  final original = command ?? copy(fixture['retained_command']);
  return offlineRecoveryRequest(
    nonce: request['nonce'],
    projectId: request['project_id'],
    planId: planId,
    requestId: original['request_id'],
    requestHash: offlinePlanRequestHash(
      projectId: request['project_id'],
      planId: planId,
      command: original,
    ),
  );
}

void main() {
  test('actual discovery and immutable identity bind exactly one account and company', () {
    final discovery = OfflineDiscovery.parse(
      fixture['context'],
      expectedAccountId: account,
    );
    expect(discovery.mode, 'bound_v2');
    expect(discovery.isBound, isTrue);
    expect(discovery.binding, binding);
    expect(discovery.toJson(), fixture['context']);
    expect(binding.headerValue, '${fixture['instance_id']}:$account');
    expect(binding.matches(OfflineBinding.fromJson(binding.toJson())), isTrue);
    expect(
      binding.hashCode,
      OfflineBinding.fromJson(binding.toJson()).hashCode,
    );
    final changed = binding.toJson()..['account_id'] = 'f' * 32;
    expect(binding.accountId, account);
    expect(binding, isNot(OfflineBinding.fromJson(changed)));
    expect(binding, isNot(OfflineBinding.fromJson(fixture['foreign_binding'])));
  });

  test('only explicit unbound discovery is accepted; missing or foreign data never falls back', () {
    final legacy = OfflineDiscovery.parse(
      fixture['unbound_context'],
      expectedAccountId: account,
    );
    expect(legacy.mode, 'unbound_legacy');
    expect(legacy.binding, isNull);
    expect(legacy.isBound, isFalse);
    for (final raw in [
      null,
      <String, dynamic>{},
      {...copy(fixture['context']), 'schema_version': 1},
      {...copy(fixture['context']), 'mode': 'unbound'},
      {...copy(fixture['context']), 'mode': 'unbound_legacy'},
      {...copy(fixture['unbound_context']), 'mode': 'bound_v2'},
      {...copy(fixture['context']), 'unexpected': true},
      {
        ...copy(fixture['context']),
        'binding': {...binding.toJson(), 'account_id': 'f' * 32},
      },
    ]) {
      expect(
        () => OfflineDiscovery.parse(raw, expectedAccountId: account),
        invalid,
      );
    }
  });

  test('binding schema rejects aliases, unknown fields and noncanonical identifiers', () {
    for (final patch in [
      {'schema_version': true},
      {'schema_version': 2},
      {'instance_id': '${fixture['instance_id']}:$account'},
      {'account_id': account.toUpperCase()},
      {'account_id': 'f' * 32},
      {'token': 'not-part-of-binding'},
    ]) {
      expect(
        () => OfflineBinding.fromJson({
          ...binding.toJson(),
          ...patch,
        }, expectedAccountId: account),
        invalid,
      );
    }
  });

  test(
    'both actual V2 grants retain exact tokens, capabilities and issue bounds',
    () {
      for (final kind in ['workspace', 'business']) {
        final original = fixture['${kind}_grant'];
        final grant = OfflineGrant.parse(
          original,
          expectedBinding: binding,
          kind: kind,
        );
        expect(grant.toJson(), original);
        expect(grant.token, original['token']);
        expect(grant.binding, binding);
        expect(
          grant.expiresAt.difference(grant.issuedAt),
          const Duration(days: 7),
        );
        expect(grant.capabilities, original['capabilities']);
        expect(() => grant.capabilities.add('other'), throwsUnsupportedError);
        final exposed = grant.raw;
        (exposed['capabilities'] as List).clear();
        (exposed['binding'] as Map)['instance_id'] = 'f' * 32;
        expect(grant.toJson(), original);
      }
      final grant = OfflineGrant.parse(
        fixture['business_grant'],
        expectedBinding: binding,
        kind: 'business',
      );
      expect(
        grant.reportProjectIds,
        fixture['business_grant']['report_project_ids'],
      );
      expect(
        grant.reportWritesEnabled,
        fixture['business_grant']['report_writes_enabled'],
      );
      expect(() => grant.reportProjectIds!.clear(), throwsUnsupportedError);
    },
  );

  test('workspace grants permit absent optional imports without admitting business scope', () {
    final local = copy(fixture['workspace_grant']);
    (local['capabilities'] as List).remove('plan_imports');
    expect(
      OfflineGrant.parse(
        local,
        expectedBinding: binding,
        kind: 'workspace',
      ).capabilities,
      isNot(contains('plan_imports')),
    );
    for (final caps in [
      [...local['capabilities'], 'time_events'],
      [...local['capabilities'], 'unknown_capability'],
      [...local['capabilities'], 'project_plans'],
      <String>[],
    ]) {
      expect(
        () => OfflineGrant.parse(
          {...local, 'capabilities': caps},
          expectedBinding: binding,
          kind: 'workspace',
        ),
        invalid,
      );
    }
    final business = copy(fixture['business_grant']);
    business['capabilities'] = local['capabilities'];
    expect(
      () => OfflineGrant.parse(
        business,
        expectedBinding: binding,
        kind: 'business',
      ),
      invalid,
    );
  });

  test('grant schema, origin, prefix, report scope and seven-day bounds fail closed', () {
    final original = copy(fixture['business_grant']);
    for (final patch in [
      {'schema_version': true},
      {'schema_version': 1},
      {'binding': fixture['foreign_binding']},
      {'token': 'offline_business_legacy'},
      {'token': 'offline_workspace_v2_opaque'},
      {'token': 'offline_business_v2_line\r\nbreak'},
      {'token': 'offline_business_v2_${'a' * 194}'},
      {'issued_at': '2026-11-09T12:00:00'},
      {'issued_at': '2026-02-30T12:00:00+00:00'},
      {'expires_at': original['issued_at']},
      {'expires_at': '2099-11-09T12:00:00+00:00'},
      {'report_writes_enabled': 1},
      {
        'report_project_ids': ['invalid'],
      },
      {
        'report_project_ids': [fixture['project_id'], fixture['project_id']],
      },
      {'extra': true},
    ]) {
      expect(
        () => OfflineGrant.parse(
          {...original, ...patch},
          expectedBinding: binding,
          kind: 'business',
        ),
        invalid,
      );
    }
    expect(
      () => OfflineGrant.parse(
        original,
        expectedBinding: binding,
        kind: 'unknown',
      ),
      invalid,
    );
    expect(
      () => OfflineGrant.parse(
        copy(original)..remove('binding'),
        expectedBinding: binding,
        kind: 'business',
      ),
      invalid,
    );
  });

  test('actual hash-only lookup excludes the retained title and geometry', () {
    final request = lookup();
    expect(request, fixture['lookup_command']);
    expect(request.keys.toSet(), {
      'schema_version',
      'nonce',
      'kind',
      'project_id',
      'plan_id',
      'request_id',
      'request_hash',
    });
    final encoded = jsonEncode(request);
    for (final private in [
      'title',
      'walls',
      'points',
      'command',
      'Synthetischer Altplan',
      '🚧',
    ]) {
      expect(encoded, isNot(contains(private)));
    }
    expect(
      offlineBindingHash(request),
      fixture['lookup_result']['lookup_hash'],
    );
    expect(request['request_hash'], fixture['lookup_result']['request_hash']);
    expect(() => request['nonce'] = 'f' * 32, throwsUnsupportedError);
    expect(
      offlineRecoveryMatch(
        fixture['lookup_result'],
        request: request,
        expectedBinding: binding,
        originalCommand: copy(fixture['retained_command']),
      ),
      fixture['lookup_result'],
    );
  });

  test('only proved integral coordinates produce a local request hash', () {
    final original = copy(fixture['retained_command']);
    expect(
      offlinePlanRequestHash(
        projectId: fixture['project_id'],
        command: original,
      ),
      fixture['lookup_result']['request_hash'],
    );
    for (final unproved in fixture['unproven_retained_commands']) {
      expect(
        () => offlinePlanRequestHash(
          projectId: fixture['project_id'],
          command: copy(unproved),
        ),
        invalid,
      );
      expect(() => lookup(command: copy(unproved)), invalid);
    }
    for (final unsupported in [0.000001, 1.5, double.infinity, double.nan]) {
      final changed = copy(original);
      changed['walls'][0]['points'][0][0] = unsupported;
      expect(
        () => offlinePlanRequestHash(
          projectId: fixture['project_id'],
          command: changed,
        ),
        invalid,
      );
    }
    final integral = copy(original);
    integral['walls'][0]['points'][0][0] = 1;
    expect(
      offlinePlanRequestHash(
        projectId: fixture['project_id'],
        command: integral,
      ),
      isNot(fixture['lookup_result']['request_hash']),
    );
    final zero = copy(original);
    zero['walls'][0]['points'][0][1] = 0.0;
    expect(
      offlinePlanRequestHash(projectId: fixture['project_id'], command: zero),
      isNot(fixture['lookup_result']['request_hash']),
    );
  });

  test('lookup response must match nonce, exact hashes, project and current binding', () {
    final request = lookup(), original = copy(fixture['lookup_result']);
    for (final patch in [
      {'schema_version': true},
      {'schema_version': 1},
      {'nonce': 'f' * 32},
      {'lookup_hash': 'f' * 64},
      {'binding': fixture['foreign_binding']},
      {'kind': 'other'},
      {'project_id': 'f' * 32},
      {'plan_id': 'f' * 32},
      {'request_id': 'f' * 32},
      {'request_hash': 'f' * 64},
      {'request_resolution': 'not_accepted'},
    ]) {
      expect(
        () => offlineRecoveryMatch(
          {...original, ...patch},
          request: request,
          expectedBinding: binding,
          originalCommand: copy(fixture['retained_command']),
        ),
        invalid,
      );
    }
    final changedBody = copy(fixture['retained_command'])
      ..['title'] = 'Anderer Altauftrag';
    expect(
      () => offlineRecoveryMatch(
        original,
        request: request,
        expectedBinding: binding,
        originalCommand: changedBody,
      ),
      invalid,
    );
  });

  test(
    'original comparison rejects newer state and numeric type substitutions',
    () {
      final request = lookup(), response = copy(fixture['lookup_result']);
      final original = copy(response['original']);
      for (final patch in [
        {'project_id': 'f' * 32},
        {'revision': 2},
        {'status': 'approved'},
        {'units': 'mm'},
        {'updated_by': 'f' * 32},
        {'updated_at': '2026-11-09T12:00:00'},
        {'title': 'Later title'},
        {'deleted': true},
      ]) {
        expect(
          () => offlineRecoveryMatch(
            {
              ...response,
              'original': {...original, ...patch},
            },
            request: request,
            expectedBinding: binding,
            originalCommand: copy(fixture['retained_command']),
          ),
          invalid,
        );
      }
      for (final coordinate in [1, 3.0]) {
        final changed = copy(original);
        changed['walls'][0]['points'][0][0] = coordinate;
        expect(
          () => offlineRecoveryMatch(
            {...response, 'original': changed},
            request: request,
            expectedBinding: binding,
            originalCommand: copy(fixture['retained_command']),
          ),
          invalid,
        );
      }
      final zero = copy(original);
      zero['walls'][0]['points'][0][1] = 0.0;
      expect(
        () => offlineRecoveryMatch(
          {...response, 'original': zero},
          request: request,
          expectedBinding: binding,
          originalCommand: copy(fixture['retained_command']),
        ),
        invalid,
      );
    },
  );

  test(
    'old full-content request variants are rejected rather than reinterpreted',
    () {
      final request = lookup(), command = copy(fixture['retained_command']);
      for (final old in [
        {...request, 'command_json': jsonEncode(command)},
        {...request, 'command': command},
        {
          'schema_version': 1,
          'nonce': request['nonce'],
          'kind': 'plan_write',
          'project_id': request['project_id'],
          'plan_id': null,
          'command_json': jsonEncode(command),
        },
      ]) {
        expect(
          () => offlineRecoveryMatch(
            fixture['lookup_result'],
            request: old,
            expectedBinding: binding,
            originalCommand: command,
          ),
          invalid,
        );
      }
      expect(
        () => offlineRecoveryRequest(
          nonce: request['nonce'],
          projectId: request['project_id'],
          requestId: command['request_id'],
          requestHash: 'invalid',
        ),
        invalid,
      );
    },
  );

  test(
    'local proof rejects malformed commands and never normalizes retained text',
    () {
      final command = copy(fixture['retained_command']);
      for (final patch in [
        {'request_id': 'invalid'},
        {'title': ' '},
        {'title': 'x' * 201},
        {'title': 'bad\uD800'},
        {'title': 'bad\uDC00'},
        {'revision': 1},
        {'extra': true},
        {
          'walls': [
            {
              'id': 'same',
              'points': [
                [1, 1],
                [1.0, 1.0],
              ],
            },
          ],
        },
        {
          'walls': [
            {
              'id': 'bool',
              'points': [
                [false, 1],
                [1, 2],
              ],
            },
          ],
        },
        {
          'walls': [
            {
              'id': 'large',
              'points': [
                [10001, 0],
                [1, 2],
              ],
            },
          ],
        },
        {
          'walls': [
            {
              'id': 'extra',
              'points': [
                [0, 0],
                [1, 2],
              ],
              'other': true,
            },
          ],
        },
      ]) {
        expect(
          () => offlinePlanRequestHash(
            projectId: fixture['project_id'],
            command: {...command, ...patch},
          ),
          invalid,
        );
      }
      final trimmed = {
        ...command,
        'title': (command['title'] as String).trim(),
      };
      expect(
        offlinePlanRequestHash(
          projectId: fixture['project_id'],
          command: trimmed,
        ),
        isNot(fixture['lookup_result']['request_hash']),
      );
      final reversed = copy(command);
      reversed['walls'][0]['points'] = (reversed['walls'][0]['points'] as List)
          .reversed
          .toList();
      expect(
        offlinePlanRequestHash(
          projectId: fixture['project_id'],
          command: reversed,
        ),
        isNot(fixture['lookup_result']['request_hash']),
      );
    },
  );

  test(
    'update proof binds project, plan, request identity and integer revision',
    () {
      final command = copy(fixture['retained_command']);
      final plan = fixture['lookup_result']['original']['id'] as String;
      final updateBody = {...command, 'revision': 1};
      final update = lookup(command: updateBody, planId: plan);
      expect(update['plan_id'], plan);
      expect(
        update['request_hash'],
        isNot(fixture['lookup_result']['request_hash']),
      );
      expect(
        () => offlineRecoveryMatch(
          fixture['lookup_result'],
          request: update,
          expectedBinding: binding,
          originalCommand: updateBody,
        ),
        invalid,
      );
      expect(
        () => lookup(command: {...command, 'revision': 0}, planId: plan),
        invalid,
      );
      expect(
        () => lookup(command: {...command, 'revision': 1.0}, planId: plan),
        invalid,
      );
      expect(() => lookup(command: command, planId: plan), invalid);
    },
  );
  test('local complete-command hashes match independently checked Python string vectors', () {
    final vectors = [
      (
        '  Original Süd 🚧  ',
        'c68c41dbfadba626da33ee8ee68e09ef91d1f710accbada60b5a71a60e4b4e45',
      ),
      (
        'e\u0301 and é',
        'f09db70ad460453973144dea9759470f10ba8582c26e8f2da3eac7c40d2430ec',
      ),
      (
        'quote" backslash\\ slash/',
        'b0dde40890fe06a92669d3febe15b0f36492ce66c3069be432266c2561ccdac5',
      ),
      (
        '\r\n\t\b\f\u0000',
        '98fd8a72743bb2b08cb59c9ef3b1093455bc49f168f97aef01f158bd3b32dcc0',
      ),
      (
        '\u2028\u2029\u0085',
        'b985b4d53a3eab2536224b8a5d78a23bef18e8d5edd97924861f8e1cbea024ff',
      ),
      (
        '\u001f\u007f',
        '03545b0f49a81605eb362a8c2aed43d259cf58f2aeaf179c841c2f3f25fd4ea6',
      ),
      (
        '漢字',
        'f9f23bde9a22803a3a48363df8f54d9d6c834176ca8d897bfdffbdfc8fadda08',
      ),
    ];
    for (final vector in vectors) {
      final command = {
        ...copy(fixture['retained_command']),
        'title': 'x${vector.$1}y',
      };
      expect(
        offlinePlanRequestHash(
          projectId: fixture['project_id'],
          command: command,
        ),
        vector.$2,
      );
    }
  });
}

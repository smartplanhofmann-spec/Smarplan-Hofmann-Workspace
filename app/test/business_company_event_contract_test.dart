import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_company_event_contract.dart';

Map<String, dynamic> companyFixture([String name = 'approval']) =>
    companyEventMap(
      jsonDecode(
        File('test/fixtures/company_events_2026.json').readAsStringSync(),
      )[name],
    );
Map<String, dynamic> copyCompany(dynamic value) =>
    companyEventMap(jsonDecode(jsonEncode(value)));

void main() {
  for (final scenario in [
    'auto',
    'approval',
    'deny',
    'project_approval',
    'external_unknown',
    'external_unconfirmed',
  ]) {
    test(
      'actual $scenario hashes, rules, histories and original command receipts',
      () {
        final f = companyFixture(scenario);
        companyEventStatus(f['status']);
        companyEventRule(f['rule']);
        companyEventRuleHistory(f['rule_history'], f['rule']['id']);
        companyEventReceipt(
          '/company-events/rules',
          companyEventMap(f['rule_command']),
          f['rule'],
        );
        for (final key in ['scan', 'scan_replay']) {
          companyEventReceipt(
            '/company-events/scan',
            companyEventMap(f['scan_command']),
            f[key],
          );
        }
        for (final kind in ['events', 'plans', 'runs']) {
          companyEventPage(f[kind], kind);
          companyEventPage(f['${kind}_after'], kind);
        }
        final plan = companyEventMap(f['plans']['items'][0]);
        companyEventPlan(plan, event: companyEventMap(f['events']['items'][0]));
        companyEventPlan(f['plan_after']);
        if (f.containsKey('approved')) {
          companyEventReceipt(
            '/company-events/plans/${plan['id']}/approve',
            companyEventMap(f['approve_command']),
            f['approved'],
          );
          for (final key in ['executed', 'execute_replay']) {
            companyEventReceipt(
              '/company-events/plans/${plan['id']}/execute',
              companyEventMap(f['execute_command']),
              f[key],
            );
          }
        }
      },
    );
  }
  test('exact 40-digit cents never pass through double or native integer', () {
    final status = companyFixture()['status'];
    final rows = companyEventConditions('cost.threshold', [
      {
        'field': 'total_cost_minor',
        'operator': 'gte',
        'value': '99999999999999999999999999999999999999,99',
      },
    ], companyEventMap(status));
    expect(rows.single['value'], '9' * 40);
    expect(
      companyEventMoney(rows.single['value']),
      '99.999.999.999.999.999.999.999.999.999.999.999.999,99 €',
    );
    expect(companyEventMoneyInput(rows.single['value']), '${'9' * 38}.99');
    for (final bad in ['1.001', '-1', '1e30', '${'9' * 39}.99', 'NaN']) {
      expect(
        () => companyEventConditions('cost.threshold', [
          {'field': 'total_cost_minor', 'operator': 'gte', 'value': bad},
        ], companyEventMap(status)),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('wrong original nonce, request hash and contradictory result never acknowledge', () {
    final f = companyFixture();
    for (final change in [
      (Map<String, dynamic> v) => v['acceptance']['request_id'] = 'a' * 32,
      (Map<String, dynamic> v) => v['acceptance']['request_hash'] = 'a' * 64,
      (Map<String, dynamic> v) =>
          v['template']['title'] = 'Changed after approval',
    ]) {
      final bad = copyCompany(f['rule']);
      change(bad);
      expect(
        () => companyEventReceipt(
          '/company-events/rules',
          companyEventMap(f['rule_command']),
          bad,
        ),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test(
    'source, event, policy original and exact action binding are checked',
    () {
      final f = companyFixture('project_approval');
      final plan = copyCompany(f['plans']['items'][0]);
      for (final change in [
        (Map<String, dynamic> v) =>
            v['context']['sources'][0]['data']['title'] =
                'Untrusted changed source',
        (Map<String, dynamic> v) =>
            v['policy']['project_policies'][0]['original_json'] += ' ',
        (Map<String, dynamic> v) =>
            v['policy']['project_policies'][0]['policy']['mode'] = 'auto',
        (Map<String, dynamic> v) => v['action_key'] = 'b' * 64,
      ]) {
        final bad = copyCompany(plan);
        change(bad);
        expect(
          () => companyEventPlan(
            bad,
            event: companyEventMap(f['events']['items'][0]),
          ),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
  test(
    'unknown external outcome remains non-executable with original claim',
    () {
      final f = companyFixture('external_unknown');
      final p = companyEventPlan(f['plan_after']);
      expect(p['outcome']['status'], 'unknown');
      expect(p['can_execute'], false);
      expect(
        p['execution']['domain_request_id'],
        f['executed']['execution']['domain_request_id'],
      );
    },
  );
  test(
    'typed conditions reject incompatible comparisons and oversized days',
    () {
      final status = companyEventMap(companyFixture()['status']);
      for (final input in [
        (
          'task.overdue',
          {'field': 'overdue_days', 'operator': 'gte', 'value': '1000001'},
        ),
        (
          'task.overdue',
          {'field': 'source_status', 'operator': 'gte', 'value': 'todo'},
        ),
        ('task.overdue', {'field': 'level', 'operator': 'eq', 'value': '1'}),
        (
          'cost.threshold',
          {'field': 'costs_complete', 'operator': 'lte', 'value': 'Ja'},
        ),
      ]) {
        expect(
          () => companyEventConditions(input.$1, [input.$2], status),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
}

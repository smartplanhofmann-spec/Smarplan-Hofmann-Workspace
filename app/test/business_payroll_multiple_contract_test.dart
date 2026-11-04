import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_multiple_case_contract.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_multiple_runs.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
Map<String, dynamic> clean(dynamic v) => copy(v)..remove('request_id');
Map<String, dynamic> values(dynamic c) {
  final d = c['details'];
  return {
    'month': d['month'],
    'running_calculation_case_id': d['running_calculation_case_ref']['id'],
    'current_annual_basis_id': d['current_annual_basis_ref']['id'],
    'previous_annual_basis_id': d['previous_annual_basis_ref']?['id'],
    'source_file_ids': c['source_file_ids'],
    'completeness_file_id': d['completeness']['evidence_ref']['id'],
    'month_events_complete': true,
    'verification_note': d['verification_note'],
    'correction_reason': c['correction_reason'],
    'components': [
      for (final p in d['components'])
        {
          'earning_id': p['earning_ref']['id'],
          'receipts': [
            for (final e in p['planned_receipts'])
              {
                'event_key': e['event_key'],
                'receipt_date': e['receipt_date'],
                'gross_minor': e['gross_minor'],
                'document_ids': [for (final r in e['document_refs']) r['id']],
              },
          ],
        },
    ],
    'annual_tax_forecasts': [
      for (final f in d['annual_tax_forecasts'])
        {
          'event_key': f['event_key'],
          'forecast_id': f['annual_tax_forecast_ref']['id'],
        },
    ],
  };
}

void main() {
  final id = fixture['saved']['employee_id'] as String;
  test('actual canonical case, source, preview and sealed receipt preserve all originals', () {
    payrollMultipleCaseSources(fixture['sources'], id, '2026-10');
    final body = payrollMultipleCaseInput(
      id,
      copy(fixture['sources']),
      values(fixture['command']),
    );
    expect({
      ...body,
      'preview_hash': fixture['preview']['preview_hash'],
    }, clean(fixture['command']));
    payrollMultipleCasePreview(fixture['preview'], body);
    payrollMultipleCaseValidator(
      clean(fixture['command']),
      preview: copy(fixture['preview']),
    )(fixture['saved']);
    payrollMultipleCaseHistory(fixture['history'], id, fixture['saved']['id']);
  });
  test(
    'real initial and paid v5 correction run receipts and deltas are bound',
    () {
      for (final f in [fixture, fixture['paid_v5_upgrade']]) {
        final input = copy(f['run_input']);
        payrollPreview(f['run_preview'], input);
        payrollReceiptValidator(
          clean(f['run_command']),
          preview: copy(f['run_preview']),
          previous: f['original_run'] == null ? null : copy(f['original_run']),
        )(f['run']);
        expect(
          payrollMultipleCaseRunInput(
            copy(f['run']['source']['multiple_one_off_case']),
          ),
          input,
        );
      }
    },
  );
  test(
    'actual unresolved multiple plan keeps null money and cannot finalize',
    () {
      final f = fixture['blocked_multiple'],
          p = payrollMultipleCalculation(f['run_preview']['calculation']);
      expect(p['scope'], 'multiple_oneoff_review_required');
      expect(p['net_minor'], isNull);
      expect(p['payout_minor'], isNull);
      expect(
        () => payrollMultipleCaseRunInput(
          copy(f['run_preview']['source']['multiple_one_off_case']),
        ),
        throwsA(isA<ApiException>()),
      );
      final bad = copy(p)..['net_minor'] = 0;
      expect(
        () => payrollMultipleCalculation(bad),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('crossed claims, event originals, employee and annual source versions fail', () {
    final mutations = <void Function(Map<String, dynamic>)>[
      (v) => v['source_snapshot']['employee']['revision']++,
      (v) => v['source_snapshot']['source_files'][0]['content_hash'] = 'f' * 64,
      (v) =>
          v['source_snapshot']['calculation_source']['components'][0]['earning']['id'] =
              'f' * 32,
      (v) =>
          v['source_snapshot']['calculation_source']['current_annual_basis']['revision']++,
      (v) =>
          v['plan']['multiple_one_off_details']['components'][0]['claim_minor']++,
      (v) =>
          v['plan']['multiple_one_off_details']['receipt_events'][0]['event_key'] =
              'e' * 32,
      (v) => v['plan']['net_minor']++,
      (v) =>
          v['plan']['multiple_one_off_details']['social_month_group']['component_allocations'] =
              [],
    ];
    for (final change in mutations) {
      final bad = copy(fixture['preview']);
      change(bad);
      expect(
        () => payrollMultipleCasePreview(bad, copy(fixture['command'])),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test(
    'frozen receipt survives editor mutation and refuses replacement original',
    () {
      final command = clean(fixture['command']),
          proof = copy(fixture['preview']),
          validate = payrollMultipleCaseValidator(command, preview: proof);
      command['details']['verification_note'] = 'later';
      proof['plan']['net_minor']++;
      validate(fixture['saved']);
      final bad = copy(fixture['saved'])..['source_hash'] = 'f' * 64;
      expect(() => validate(bad), throwsA(isA<ApiException>()));
    },
  );
  test(
    'real schema4 ledger preserves actual monthly groups and exports',
    () async {
      for (final f in [fixture, fixture['paid_v5_upgrade']])
        await payrollLedgerSnapshot(f['ledger'], f['run']['employee_id'], 2026);
    },
  );
  test('complete original cannot lose its sole tax forecast behind a malformed envelope', () {
    final raw = copy(fixture['preview']), body = copy(fixture['command']);
    body['details']['annual_tax_forecasts'] = [];
    raw['source_snapshot']['details']['annual_tax_forecasts'] = [];
    raw['source_snapshot']['calculation_source']['annual_tax_forecasts'] = [];
    expect(
      () => payrollMultipleCasePreview(raw, body),
      throwsA(isA<ApiException>()),
    );
  });
  test('new Source5 contract versions require exact integer encoding', () {
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['source_contract_version'] = 1.0,
      (v) => v['source_contract_version'] = '1',
    ]) {
      final bad = copy(fixture['saved']['plan']);
      change(bad);
      expect(
        () => payrollMultipleCalculation(bad),
        throwsA(isA<ApiException>()),
      );
    }
    final bad = copy(fixture['run_preview']);
    bad['source']['source_schema_version'] = 5.0;
    expect(
      () => payrollMultipleSource(bad, copy(fixture['run_input'])),
      throwsA(isA<ApiException>()),
    );
  });
  test('explicit exact EUR cents never infer or round amounts', () {
    expect(payrollMultipleMoney('12,34'), 1234);
    for (final x in ['', '0', '1.001', '-1', '1e3'])
      expect(() => payrollMultipleMoney(x), throwsA(isA<ApiException>()));
  });
}

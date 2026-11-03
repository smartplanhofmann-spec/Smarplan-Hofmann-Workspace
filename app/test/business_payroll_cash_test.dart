import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_payroll_cash.dart';
import 'package:smartplan_office/business_payroll_cash_page.dart';
import 'package:smartplan_office/business_accounting_euer.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_cash.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
final employee = f['employee']['id'] as String, key = 'payroll-cash-$employee';
Map<String, dynamic> netValues() => {
  'account_id': f['account']['id'],
  'parts_0': ['0'],
  'reason': f['body']['reason'],
};
Map<String, dynamic> remittanceValues() => {
  for (final e in copy(f['remittance_body']['sources'][0]['amounts']).entries)
    'remit_0_${e.key}': (e.value / 100).toStringAsFixed(2),
  ...copy(f['remittance_body']['settlement']),
  'account_id': f['account']['id'],
  'reason': f['remittance_body']['reason'],
  'amount_minor': (f['remittance_body']['settlement']['amount_minor'] / 100)
      .toStringAsFixed(2),
};

class CashApi extends OfficeApi {
  CashApi() : super(apiVersion: 'v1') {
    token = 'synthetic-payroll-cash-session';
  }
  bool hr = true, finance = true, writes = true, lose = false, history = false;
  String instance = f['state']['instance_id'];
  final posts = <Map<String, dynamic>>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': [
          'payroll_actual_cash',
          'accounting_euer',
          'accounting_prejournal',
        ],
        'capabilities': [
          'business_payroll_cash',
          'business_accounting_euer',
          'business_accounting',
        ],
        'permissions': [
          if (hr) ...['personnel.read', 'personnel.approve'],
          'accounting.read',
          'accounting.prepare',
          'accounting.admin',
          if (finance) 'finance.read',
          'finance.write',
        ],
      };
    if (path == '/api/business/payroll/cash')
      return {
        ...copy(f['state']),
        'batches': history ? [f['batch']] : [],
        'instance_id': instance,
        'writes_allowed': writes,
      };
    if (path.startsWith('/api/business/payroll/cash/sources?'))
      return {...copy(f['sources']), 'instance_id': instance};
    if (path.startsWith('/api/business/payroll/cash/batches/'))
      return copy(f['detail']);
    if (path == '/api/business/accounting/accounts')
      return {
        'items': [f['account']],
      };
    if (path == '/api/business/payroll/cash/preview') return copy(f['preview']);
    if (body != null) {
      posts.add(copy(body));
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Synthetic lost reply');
      }
      return copy(f['batch']);
    }
    throw StateError(path);
  }
}

Future<BusinessSession> session(CashApi api) async {
  final s = BusinessSession(api: api);
  await s.load();
  return s;
}

void main() {
  test('net uses exact actual source parts and excludes invented gross and tax payments', () {
    final body = payrollCashInput(
      employee,
      copy(f['state']),
      copy(f['sources']),
      [copy(f['account'])],
      netValues(),
      kind: 'net',
      selected: businessItems(f['sources']['net_sources']),
      batchId: f['body']['batch_id'],
    );
    expect(body, f['body']);
    expect(body['settlement'], null);
    expect(body.containsKey('gross_minor'), false);
    expect(
      () => payrollCashInput(
        employee,
        copy(f['state']),
        copy(f['sources']),
        [copy(f['account'])],
        {...netValues(), 'parts_0': []},
        kind: 'net',
        selected: businessItems(f['sources']['net_sources']),
        batchId: f['body']['batch_id'],
      ),
      throwsA(isA<ApiException>()),
    );
  });
  test('all remittance values including zeros and exact original settlement are explicit', () {
    final values = remittanceValues();
    Map<String, dynamic> build(Map<String, dynamic> v) => payrollCashInput(
      employee,
      copy(f['state']),
      copy(f['sources']),
      [copy(f['account'])],
      v,
      kind: 'remittance',
      selected: businessItems(f['sources']['remittance_sources']),
      batchId: f['remittance_body']['batch_id'],
    );
    expect(build(values), f['remittance_body']);
    for (final patch in [
      {'remit_0_employee_tax': ''},
      {'amount_minor': '1.00'},
      {'source_file_id': 'f' * 32},
    ])
      expect(() => build({...values, ...patch}), throwsA(isA<ApiException>()));
    expect(payrollCashMinor('0,00'), 0);
    expect(() => payrollCashMinor('0.001'), throwsA(isA<ApiException>()));
  });
  test('known void keeps historical money account even when current bank inactive or revised', () {
    final previous = copy(f['detail']),
        body = payrollCashInput(
          employee,
          copy(f['state']),
          copy(f['sources']),
          [
            {...copy(f['account']), 'active': false, 'revision': 2},
          ],
          {
            'reason': 'Originalbelegter Irrtum',
            'correction_file_id': f['sources']['evidence_files'][0]['id'],
          },
          kind: 'net',
          batchId: previous['id'],
          previous: previous,
          action: 'void',
        );
    expect(body['account_revision'], 1);
    expect(body['account_id'], f['account']['id']);
    expect(body['sources'], isEmpty);
    expect(body['settlement'], null);
  });
  test('public finance projection rejects personal payload fields and changed money totals', () {
    payrollCashPublic(f['batch']['public_source']);
    expect(
      () => payrollCashPublic({
        ...copy(f['batch']['public_source']),
        'employee_id': employee,
      }),
      throwsA(isA<ApiException>()),
    );
    final bad = copy(f['batch']['public_source']);
    bad['cash_movements'][0]['categories']['payroll_net'] = '5000.00';
    expect(() => payrollCashPublic(bad), throwsA(isA<ApiException>()));
  });
  test('financial form requires only explicit SKR04 accounts and preserves source facts', () {
    final form = euerForm('payroll_cash', copy(f['batch']['public_source']));
    expect(
      form.fields.any(
        (v) => [
          'cash_date',
          'amount',
          'euer_date',
          'business_net',
        ].contains(v.name),
      ),
      false,
    );
    expect(form.initial['payroll_payroll_net'], null);
    expect(
      form.payload({'payroll_payroll_net': '6020'}),
      f['euer_body']['payload'],
    );
    expect(
      () => form.payload({'payroll_payroll_net': ''}),
      throwsA(isA<FormatException>()),
    );
    euerReceiptValidator({
      ...copy(f['euer_body']),
      'preview_hash': f['euer_preview']['preview_hash'],
      'confirmation': true,
    }, copy(f['euer_preview']))(f['euer_entry']);
  });
  test('private preview and frozen receipt bind exact public proof, revision and selected source count', () {
    payrollCashPreview(f['preview'], copy(f['body']));
    final proof = copy(f['preview']),
        validate = payrollCashValidator(copy(f['body']), proof);
    proof['public_source']['cash_movements'][0]['amount'] = '0.00';
    validate(f['batch']);
    for (final patch in [
      {'revision': 2},
      {'instance_id': 'f' * 32},
      {'private_hash': 'f' * 64},
      {'public_source': f['remittance_batch']['public_source']},
    ])
      expect(
        () => validate({...copy(f['batch']), ...patch}),
        throwsA(isA<ApiException>()),
      );
    expect(
      () => payrollCashPreview({
        ...copy(f['preview']),
        'private_source_count': 0,
      }, copy(f['body'])),
      throwsA(isA<ApiException>()),
    );
  });
  test('lost reply survives HR loss, restore gate and instance mismatch with identical nonce and body', () async {
    final api = CashApi()..lose = true, s = await session(api);
    addTearDown(s.dispose);
    addTearDown(api.dispose);
    final body = {
      ...copy(f['body']),
      'preview_hash': f['preview']['preview_hash'],
      'confirmation': true,
    };
    await expectLater(
      s.command(
        key,
        '/payroll/cash/batches',
        body,
        validateResult: payrollCashValidator(body, copy(f['preview'])),
      ),
      throwsA(isA<ApiException>()),
    );
    api.hr = false;
    await expectLater(
      s.repeatPayrollCashCommand(employee),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    api.hr = true;
    api.writes = false;
    await expectLater(
      s.repeatPayrollCashCommand(employee),
      throwsA(isA<ApiException>()),
    );
    expect(s.pending(key), true);
    api.writes = true;
    api.instance = 'f' * 32;
    await expectLater(
      s.repeatPayrollCashCommand(employee),
      throwsA(isA<ApiException>()),
    );
    expect(api.posts.length, 1);
    api.instance = f['state']['instance_id'];
    await s.repeatPayrollCashCommand(employee);
    expect(api.posts[0], api.posts[1]);
    expect(s.pending(key), false);
  });
  test('financial classification requires no personnel grant while private adoption remains denied', () async {
    final api = CashApi()..hr = false, s = await session(api);
    addTearDown(s.dispose);
    addTearDown(api.dispose);
    expect(businessEuerWritable(s), true);
    expect(payrollCashReadable(s), false);
  });
  testWidgets(
    'actual remittance form leaves all five amounts, payment day and total empty',
    (tester) async {
      tester.view.physicalSize = const Size(1400, 1600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = CashApi(), s = await session(api);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollCashPage(
            session: s,
            employee: copy(f['employee']),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Belegte Abführungen übernehmen'));
      await tester.pumpAndSettle();
      final choices = tester.widgetList<CheckboxListTile>(
        find.byType(CheckboxListTile),
      );
      expect(choices.every((v) => v.value == false), true);
      await tester.tap(find.byType(CheckboxListTile).first);
      await tester.tap(find.text('Zahlungsteile ausdrücklich auswählen'));
      await tester.pumpAndSettle();
      for (final name in [
        ...payrollRemittance.keys.map((k) => 'remit_0_$k'),
        'paid_on',
        'amount_minor',
      ]) {
        final field = tester.widget<TextFormField>(
          find.byKey(ValueKey('business-field-$name')),
        );
        expect(field.controller!.text, '');
      }
      expect(api.posts, isEmpty);
      await tester.pumpWidget(const SizedBox());
      s.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'open private payroll receipt clears when finance access is revoked',
    (tester) async {
      tester.view.physicalSize = const Size(1400, 1600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = CashApi()..history = true, s = await session(api);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPayrollCashPage(
            session: s,
            employee: copy(f['employee']),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Privaten Übernahmenachweis öffnen'));
      await tester.pumpAndSettle();
      expect(find.text('Privater Lohnzahlungsnachweis'), findsOneWidget);
      expect(find.textContaining('Geschütztes Original:'), findsWidgets);
      api.finance = false;
      await s.load();
      await tester.pumpAndSettle();
      expect(
        find.text('Private Zahlungsnachweise sind nicht mehr freigegeben.'),
        findsOneWidget,
      );
      expect(find.textContaining('Geschütztes Original:'), findsNothing);
      await tester.pumpWidget(const SizedBox());
      s.dispose();
      api.dispose();
    },
  );
  test('documented negative employee payment retains original inbound part without fabricated gross cash', () {
    final n = copy(f['negative']),
        body = payrollCashInput(
          n['employee']['id'],
          copy(n['state']),
          copy(n['sources']),
          [copy(n['account'])],
          {
            'account_id': n['account']['id'],
            'parts_0': ['1'],
            'reason': n['body']['reason'],
          },
          kind: 'net',
          selected: businessItems(n['sources']['net_sources']),
          batchId: n['body']['batch_id'],
        );
    expect(body, n['body']);
    payrollCashPreview(n['preview'], body);
    expect(
      n['sources']['net_sources'][0]['payments'][1]['amount_minor'],
      -1871,
    );
    expect(n['batch']['public_source']['cash_movements'][0]['direction'], 'in');
    expect(n['batch']['public_source']['cash_movements'][0]['amount'], '18.71');
  });
}

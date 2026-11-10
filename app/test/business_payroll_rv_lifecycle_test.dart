import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_payroll.dart';
import 'package:smartplan_office/business_payroll_rv_lifecycle.dart';
import 'package:smartplan_office/business_session.dart';

final fixture = jsonDecode(
  File('test/fixtures/payroll_rv_lifecycle.json').readAsStringSync(),
) as Map<String, dynamic>;
final cases = businessItems(fixture['cases']);
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
Map<String, dynamic> values(Map<String, dynamic> c) {
  final a = businessMap(c['input']['details']['assessment']),
      r = businessMap(a['revocation']);
  return {
    ...a,
    'exempt_from': a['established_exemption']['effective_from'],
    'original_profile_id': payrollRvSelection(
      a['established_exemption']['profile_ref'],
    ),
    'exemption_file_id': a['established_exemption']['evidence_ref']['id'],
    'established_status_confirmed': true,
    'request_state': r.isEmpty ? 'none' : 'received',
    'received_on': r['received_on'] ?? '',
    'request_format': r['request_format'] ?? '',
    'request_file_id': r['request_ref']?['id'] ?? '',
    'notification_received_on': r['notification_received_on'] ?? '',
    'notification_file_id': r['notification_ref']?['id'] ?? '',
    'authority_status': r['authority_status'] ?? '',
    'objection_deadline_on': r['objection_deadline_on'] ?? '',
    'deadline_file_id': r['deadline_ref']?['id'] ?? '',
    'deadline_review_confirmed': r['deadline_review_confirmed'] ?? false,
    'authority_status_on': r['authority_status_on'] ?? '',
    'authority_file_id': r['authority_evidence_ref']?['id'] ?? '',
    'procedure_note': r['review_note'] ?? '',
  };
}

class RvApi extends OfficeApi {
  RvApi() : super(apiVersion: 'v1') {
    token = 'synthetic-rv-session';
  }
  bool read = true,
      approve = true,
      sourceApprove = true,
      paused = false,
      lose = false,
      wrongReceipt = false;
  final sent = <Map<String, dynamic>>[];
  Map<String, dynamic> data = cases.last;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['payroll_rv_lifecycle', 'organization_modules'],
        'capabilities': ['business_payroll_rv_lifecycle'],
        'permissions': [
          if (read) 'personnel.read',
          if (approve) 'personnel.approve',
        ],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final name in BusinessSession.organizationSections)
              name: {
                'visible': true,
                'enabled': name != 'personnel' || !paused,
              },
          },
        },
      };
    if (path == '/api/me') return {'id': 'a' * 32};
    if (path.startsWith('/api/business/payroll/rv-lifecycle/sources?'))
      return copy(data['sources'])
        ..['can_approve'] = sourceApprove
        ..['writes_enabled'] = !paused;
    if (path == '/api/business/payroll/rv-lifecycle') {
      sent.add(copy(body));
      if (lose) {
        lose = false;
        throw const ApiException(
          0,
          'Angenommene Antwort synthetisch verloren.',
        );
      }
      final result = copy(data['record']);
      if (wrongReceipt)
        result['details']['assessment']['review_note'] =
            'Replaced original review';
      return result;
    }
    throw StateError(path);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('an ID alone or another revision cannot float to the newest original', () {
    final c = cases.last, s = copy(c['sources']);
    for (final selection in [
      c['record']['id'],
      payrollRvSelection({...copy(c['record']), 'revision': 2}),
      payrollRvSelection({...copy(c['record']), 'content_hash': 'f' * 64}),
    ]) {
      expect(
        () => payrollRvProfileBinding(s, {'rv_lifecycle_id': selection}),
        throwsA(isA<ApiException>()),
      );
    }
    final input = values(c)
      ..['original_profile_id'] =
          c['input']['details']['assessment']['established_exemption']['profile_ref']['id'];
    expect(
      () => payrollRvInput(copy(c['sources_before']), input),
      throwsA(isA<ApiException>()),
    );
  });
  test('pending procedure may retain an actually reviewed future deadline', () {
    final a = copy(cases.last['input']['details']['assessment']);
    a['target_month'] = '2026-08';
    a['reviewed_as_of'] = '2026-08-01';
    a['revocation'].addAll({
      'authority_status': 'pending',
      'authority_status_on': null,
      'authority_evidence_ref': null,
    });
    expect(
      payrollRvAssessment(a)['revocation']['objection_deadline_on'],
      '2026-08-21',
    );
    a['revocation']['notification_received_on'] = '2026-08-02';
    expect(() => payrollRvAssessment(a), throwsA(isA<ApiException>()));
  });
  for (final c in cases) {
    test(
      'actual ${c['name']} originals bind native input, preview and accepted receipt',
      () {
        final s = payrollRvSources(
              copy(c['sources_before']),
              c['employee']['id'],
            ),
            b = payrollRvInput(s, values(c));
        expect(payrollRvPreviewInput(b), c['input']);
        final p = payrollRvPreview(copy(c['preview']), b);
        payrollRvValidator({...b, 'preview_hash': p['preview_hash']}, p)(
          copy(c['record']),
        );
        expect(
          payrollRvRecord(copy(c['record']), c['employee']['id']),
          c['record'],
        );
        expect(p['plan']['can_bind_payroll'], c['name'] != 'pending');
      },
    );
  }
  test(
    'changed original source, rule, decision and preview hashes fail closed',
    () {
      final c = cases.last;
      for (final change in <void Function(Map<String, dynamic>)>[
        (v) => v['source_snapshot']['source_files'][0]['sha256'] = 'f' * 64,
        (v) => v['plan']['rules_sha256'] = 'f' * 64,
        (v) => v['preview_hash'] = 'f' * 64,
        (v) => v['plan']['external_transmission'] = true,
        (v) => v['plan']['minijob_rv_exempt'] = true,
      ]) {
        final v = copy(c['preview']);
        change(v);
        expect(
          () => payrollRvPreview(v, copy(c['input'])),
          throwsA(isA<ApiException>()),
        );
      }
      final pending = copy(cases[1]['preview']);
      pending['plan'].addAll({
        'can_bind_payroll': true,
        'can_determine': true,
        'blockers': [],
        'minijob_rv_exempt': false,
        'status': 'compulsory_after_revocation',
      });
      expect(
        () => payrollRvPreview(pending, copy(cases[1]['input'])),
        throwsA(isA<ApiException>()),
      );
    },
  );
  test('private source identity, complete prefix and exact numeric versions are mandatory', () {
    final c = cases.last;
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v['employee']['id'] = 'f' * 32,
      (v) => v['prior_assessment_refs'] = [],
      (v) => v['files'][0]['employee_id'] = 'f' * 32,
      (v) => v['history'][0]['source_contract_version'] = true,
    ]) {
      final v = copy(c['sources']);
      change(v);
      expect(
        () => payrollRvSources(v, c['employee']['id']),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('the explicit RV original is part of the complete accepted profile', () {
    final c = cases.last, s = copy(c['sources']);
    expect(() => payrollRvProfileBinding(s, {}), throwsA(isA<ApiException>()));
    final binding = payrollRvProfileBinding(s, {
      'rv_lifecycle_id': payrollRvSelection(c['record']),
    });
    expect(
      binding['rv_lifecycle_ref']['content_hash'],
      c['record']['content_hash'],
    );
    final validate = payrollReceiptValidator(
      copy(c['profile_command']),
      original: copy(businessItems(s['files']).first),
    );
    validate(copy(c['profile']));
    for (final change in <void Function(Map<String, dynamic>)>[
      (v) => v.remove('rv_lifecycle_ref'),
      (v) => v['rv_lifecycle_source_contract_version'] = true,
      (v) => v['rv_lifecycle_ref']['content_hash'] = 'f' * 64,
    ]) {
      final v = copy(c['profile']);
      change(v);
      expect(() => validate(v), throwsA(isA<ApiException>()));
    }
  });
  test('lost accepted answer repeats exact bytes after a pause and rejects a replaced answer', () async {
    final api = RvApi()..lose = true;
    final current = BusinessSession(api: api);
    addTearDown(current.dispose);
    addTearDown(api.dispose);
    await current.load();
    final c = cases.last,
        b = copy(c['command'])..remove('request_id'),
        id = c['employee']['id'],
        key = 'payroll-rv-lifecycle-$id';
    await expectLater(
      current.command(
        key,
        payrollRvPath,
        b,
        validateResult: payrollRvValidator(b, copy(c['preview'])),
      ),
      throwsA(isA<ApiException>()),
    );
    api.paused = true;
    api.wrongReceipt = true;
    await expectLater(
      current.repeatPayrollRvCommand(id),
      throwsA(isA<ApiException>()),
    );
    expect(current.pending(key), true);
    api.wrongReceipt = false;
    await current.repeatPayrollRvCommand(id);
    expect(current.pending(key), false);
    expect(api.sent, hasLength(3));
    expect(
      api.sent.every((v) => jsonEncode(v) == jsonEncode(api.sent.first)),
      true,
    );
  });
  test(
    'pending replay rechecks current private approval before sending',
    () async {
      final api = RvApi()..lose = true;
      final session = BusinessSession(api: api);
      addTearDown(session.dispose);
      addTearDown(api.dispose);
      await session.load();
      final c = cases.last,
          b = copy(c['command'])..remove('request_id'),
          id = c['employee']['id'];
      await expectLater(
        session.command(
          'payroll-rv-lifecycle-$id',
          payrollRvPath,
          b,
          validateResult: payrollRvValidator(b, copy(c['preview'])),
        ),
        throwsA(isA<ApiException>()),
      );
      api.approve = false;
      await expectLater(
        session.repeatPayrollRvCommand(id),
        throwsA(isA<ApiException>()),
      );
      expect(api.sent, hasLength(1));
      api.approve = true;
      api.sourceApprove = false;
      await expectLater(
        session.repeatPayrollRvCommand(id),
        throwsA(isA<ApiException>()),
      );
      expect(api.sent, hasLength(1));
    },
  );
  for (final width in [390.0, 1100.0]) {
    testWidgets(
      'private RV page and explicit original form render at $width pixels',
      (tester) async {
        tester.view.physicalSize = Size(width, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final api = RvApi();
        final current = BusinessSession(api: api);
        var disposed = false;
        addTearDown(() {
          if (!disposed) current.dispose();
        });
        addTearDown(api.dispose);
        await current.load();
        await tester.pumpWidget(
          MaterialApp(
            home: BusinessPayrollRvPage(
              session: current,
              employee: copy(cases.last['employee']),
              onOriginal: (_) async {},
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('RV-Pflicht nach belegter Aufhebung'), findsOneWidget);
        expect(tester.takeException(), isNull);
        await tester.tap(find.text('Prüfstand mit Originalen fortschreiben'));
        await tester.pumpAndSettle();
        expect(
          find.text('Minijob-RV anhand der Originale prüfen'),
          findsOneWidget,
        );
        expect(
          find.text('Tatsächlicher Abrechnungsmonat (JJJJ-MM)'),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
        api.read = false;
        await current.load();
        await tester.pumpAndSettle();
        expect(
          find.text('Minijob-RV anhand der Originale prüfen'),
          findsNothing,
        );
        expect(find.text('Keine private Personalfreigabe.'), findsOneWidget);
        await tester.pumpWidget(const SizedBox.shrink());
        current.dispose();
        disposed = true;
        await tester.pumpAndSettle();
      },
    );
  }
}

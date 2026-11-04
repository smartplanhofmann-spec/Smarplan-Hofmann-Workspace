import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_payroll_statements.dart';
import 'package:smartplan_office/mail_attachment_preview.dart';

final f = jsonDecode(
  File('test/fixtures/payroll_statements_v7.json').readAsStringSync(),
) as Map<String, dynamic>;
Map<String, dynamic> copy(dynamic v) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(v)) as Map);
dynamic order(dynamic v) => v is List
    ? v.map(order).toList()
    : v is Map
    ? {for (final k in v.keys.map((v) => '$v').toList()..sort()) k: order(v[k])}
    : v;
Future<void> rehash(Map<String, dynamic> v) async {
  final base = copy(v)
    ..remove('statement_hash')
    ..remove('pdf_sha256')
    ..remove('pdf_size');
  v['statement_hash'] = await payrollStatementHash(
    utf8.encode(jsonEncode(order(base))),
  );
}

class MultipleOwnApi extends OfficeApi {
  MultipleOwnApi() : super(apiVersion: 'v1') {
    token = 'synthetic-source5-own';
  }
  bool allowed = true;
  Completer<Uint8List>? held;
  bool revokeOnBytes = false;
  final paths = <String>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    paths.add(path);
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'storage_version': 10,
        'readonly': false,
        'features': ['german_payroll_2026', 'payroll_employee_statements'],
        'capabilities': ['business_payroll'],
        'permissions': [if (allowed) 'time.own'],
        'organization': {
          'modules': {
            'personnel': {'enabled': true, 'visible': true},
          },
        },
      };
    if (path == '/api/me') return f['actor'];
    if (path == '/api/business/employees') return [f['employee']];
    if (!allowed) throw const ApiException(403, 'Freigabe entzogen');
    if (path.startsWith('/api/business/payroll/employee-statements?'))
      return copy(f['page']);
    if (path.contains('/payroll/employee-statements/') &&
        path.endsWith('/history'))
      return copy(f['history']);
    if (path.contains('/payroll/employee-statements/'))
      return {
        'employee_id': f['employee']['id'],
        'can_export': true,
        'statement': copy(
          path.contains('revision=1') ? f['previous'] : f['statement'],
        ),
      };
    throw StateError('Private source route used: $path');
  }

  @override
  Future<Uint8List> bytes(
    String path, {
    required String mediaType,
    int maxBytes = 20 * 1024 * 1024,
  }) async {
    paths.add(path);
    if (revokeOnBytes) allowed = false;
    if (held != null) return held!.future;
    if (path.contains('/json?')) {
      expect(mediaType, 'application/json');
      return base64Decode(f['json_base64']);
    }
    expect(mediaType, 'application/pdf');
    return base64Decode(f['pdf_base64']);
  }
}

Future<void> openPage(
  WidgetTester tester,
  MultipleOwnApi api,
  BusinessSession session, {
  MailAttachmentExporter? exporter,
}) async {
  await session.load();
  await tester.pumpWidget(
    MaterialApp(
      home: BusinessPayrollStatementsPage(
        session: session,
        employee: copy(f['employee']),
        exporter: exporter,
      ),
    ),
  );
  await tester.pumpAndSettle();
  await tester.tap(find.text('Lohnnachweis ansehen'));
  await tester.pumpAndSettle();
}

void main() {
  test(
    'actual Source5 schema4 JSON and PDF retain exact original employee values',
    () async {
      await payrollStatement(f['statement'], f['employee']['id']);
      await payrollStatement(f['previous'], f['employee']['id']);
      await payrollStatementPage(f['history'], f['employee']['id']);
      final statement = copy(f['statement']);
      final document = await payrollStatementJsonAttachment(
        base64Decode(f['json_base64']),
        statement,
      );
      expect(document.filename, 'lohnnachweis-2026-10-v2.json');
      expect(document.mediaType, 'application/json');
      expect(jsonDecode(utf8.decode(document.bytes)), statement);
      await payrollStatementAttachment(
        base64Decode(f['pdf_base64']),
        statement,
      );
      await payrollStatementAttachment(
        base64Decode(f['previous_pdf_base64']),
        copy(f['previous']),
      );
    },
  );
  test(
    'rehashing cannot authorize private IDs or inconsistent version and money',
    () async {
      for (final change in <void Function(Map<String, dynamic>)>[
        (v) => v['event_key'] = 'a' * 32,
        (v) => v['one_off_summary']['component_key'] = 'b' * 32,
        (v) => v['one_off_summary']['annual_pay_before_minor'] = 1,
        (v) =>
            v['one_off_summary']['employee_contributions']['earning_ref'] = {},
        (v) => v['schema_version'] = 3,
        (v) =>
            v['calculation']['rule_version'] = 'de_2026_oneoff_composition_v6',
        (v) => v['calculation']['scope'] = 'regular_standard_oneoff',
        (v) => v['calculation']['payroll_calculation_complete'] = false,
        (v) => v['one_off_summary']['amount_minor']++,
        (v) => v['one_off_summary']['employee_social_total_minor']++,
      ]) {
        final bad = copy(f['statement']);
        change(bad);
        await rehash(bad);
        await expectLater(
          payrollStatement(bad, f['employee']['id']),
          throwsA(isA<ApiException>()),
        );
      }
    },
  );
  test('JSON requires entire selected original even for a different valid statement', () async {
    final changed = copy(f['statement'])..['employee_name'] = 'Changed name';
    await rehash(changed);
    for (final bytes in [
      Uint8List.fromList([255, 254]),
      Uint8List.fromList(
        utf8.encode(
          utf8
              .decode(base64Decode(f['json_base64']))
              .replaceFirst(
                '{',
                '{\"employee_name\":\"PRIVATE-DUPLICATE-SHADOW\",',
              ),
        ),
      ),
      Uint8List.fromList(utf8.encode('{}')),
      Uint8List.fromList(utf8.encode(jsonEncode(f['previous']))),
      Uint8List.fromList(utf8.encode(jsonEncode(changed))),
      Uint8List(1024 * 1024 + 1),
    ]) {
      await expectLater(
        payrollStatementJsonAttachment(bytes, copy(f['statement'])),
        throwsA(isA<ApiException>()),
      );
    }
  });
  testWidgets(
    '390px own Source5 JSON export and history never request private originals',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = MultipleOwnApi();
      final active = BusinessSession(api: api);
      VerifiedMailAttachment? saved;
      await openPage(
        tester,
        api,
        active,
        exporter: (context, document, guard) async {
          expect(guard(), true);
          saved = document;
          return MailAttachmentExportResult.saved;
        },
      );
      await tester.scrollUntilVisible(
        find.text('Einmalzahlung / sonstiger Bezug'),
        500,
      );
      expect(find.text('Brutto der Einmalzahlung'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Eigenen JSON-Lohnnachweis herunterladen'),
        500,
      );
      await tester.tap(find.text('Eigenen JSON-Lohnnachweis herunterladen'));
      await tester.pumpAndSettle();
      expect(jsonDecode(utf8.decode(saved!.bytes)), f['statement']);
      expect(tester.takeException(), null);
      await tester.scrollUntilVisible(find.text('Beleghistorie öffnen'), 500);
      await tester.tap(find.text('Beleghistorie öffnen'));
      await tester.pumpAndSettle();
      expect(find.text('Diese Fassung ansehen'), findsNWidgets(2));
      await tester.tap(find.text('Diese Fassung ansehen').first);
      await tester.pumpAndSettle();
      expect(find.text('Einmalzahlung / sonstiger Bezug'), findsNothing);
      expect(
        api.paths.any(
          (p) => RegExp(
            r'/payroll/(runs|profiles|facts|annual-facts|multiple-one-off-cases)|/personnel/files',
          ).hasMatch(p),
        ),
        false,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      active.dispose();
    },
  );
  testWidgets('revocation during JSON download clears view and cannot export', (
    tester,
  ) async {
    final api = MultipleOwnApi()..revokeOnBytes = true;
    final session = BusinessSession(api: api);
    var exports = 0;
    await openPage(
      tester,
      api,
      session,
      exporter: (context, document, guard) async {
        exports++;
        return MailAttachmentExportResult.saved;
      },
    );
    await tester.scrollUntilVisible(
      find.text('Eigenen JSON-Lohnnachweis herunterladen'),
      500,
    );
    await tester.tap(find.text('Eigenen JSON-Lohnnachweis herunterladen'));
    await tester.pumpAndSettle();
    expect(exports, 0);
    expect(find.text('Netto'), findsNothing);
    expect(tester.takeException(), null);
    await tester.pumpWidget(const SizedBox.shrink());
    session.dispose();
  });
  testWidgets('paused or changed-token session discards late JSON response', (
    tester,
  ) async {
    for (final pause in [true, false]) {
      final api = MultipleOwnApi()..held = Completer<Uint8List>();
      final session = BusinessSession(api: api);
      var exports = 0;
      await openPage(
        tester,
        api,
        session,
        exporter: (context, document, guard) async {
          exports++;
          return MailAttachmentExportResult.saved;
        },
      );
      await tester.scrollUntilVisible(
        find.text('Eigenen JSON-Lohnnachweis herunterladen'),
        500,
      );
      await tester.tap(find.text('Eigenen JSON-Lohnnachweis herunterladen'));
      for (
        var i = 0;
        i < 25 && !api.paths.any((p) => p.contains('/json?'));
        i++
      )
        await tester.pump(const Duration(milliseconds: 10));
      expect(api.paths.any((p) => p.contains('/json?')), true);
      if (pause) {
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      } else {
        api.token = 'different-session';
        await session.load();
      }
      api.held!.complete(base64Decode(f['json_base64']));
      await tester.pumpAndSettle();
      expect(exports, 0);
      expect(find.text('Netto'), findsNothing);
      expect(tester.takeException(), null);
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
    }
  });
}

import 'dart:convert';
import 'dart:typed_data';

import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_personnel_workflow.dart';
import 'package:smartplan_office/business_session.dart';

const employeeId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const owner = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const worker = 'cccccccccccccccccccccccccccccccc';
const fileId = 'dddddddddddddddddddddddddddddddd';
final png = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
);
Map<String, dynamic> copy(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;
Map<String, dynamic> preview() => {
  'source_hash': 'a' * 64,
  'snapshot': {
    'employee': {'id': employeeId},
    'month': '2026-11',
  },
};

class PersonnelApi extends OfficeApi {
  PersonnelApi() : super(apiVersion: 'v1') {
    token = 'synthetic-personnel-session';
  }
  bool read = true, write = true, lose = true;
  int generation = 1, created = 0;
  final commands = <Map<String, dynamic>>[];
  Map<String, dynamic>? accepted;
  Map<String, dynamic> file() => {
    'id': fileId,
    'employee_id': employeeId,
    'purpose': 'personnel',
    'owner_visible': 0,
    'filename': 'Vertrag.png',
    'media_type': 'image/png',
    'size': png.length,
    'sha256': 'a' * 64,
  };
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'storage_version': 8,
        'generation': generation,
        'readonly': false,
        'capabilities': ['business_personnel_workflow', 'business_planning'],
        'features': ['personnel_preparation'],
        'permissions': <String>[
          if (read) 'personnel.read',
          if (write) 'personnel.write',
          'time.own',
        ],
      };
    if (path == '/api/me') return {'id': owner};
    if (path == '/api/business/employees')
      return [
        {
          'id': employeeId,
          'user_id': worker,
          'name': 'Synthetischer Mitarbeiter',
        },
      ];
    if (path.startsWith('/api/business/personnel/files?'))
      return {
        'employee_id': employeeId,
        'items': created > 0 ? [file()] : [],
      };
    if (RegExp(
      r'^/api/business/personnel/(agreements|expenses|payroll-preparations)\?',
    ).hasMatch(path))
      return {'employee_id': employeeId, 'items': []};
    if (path == '/api/business/personnel/files') {
      commands.add(copy(body!));
      if (!write || !read)
        throw const ApiException(403, 'Personalrecht entzogen');
      accepted ??= copy(body);
      expect(body, accepted);
      if (created == 0) created = 1;
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      return file();
    }
    throw StateError('Unexpected API $path');
  }
}

class ExpenseApprovalApi extends PersonnelApi {
  bool approve = true;
  bool modernServer = true;
  String viewer = owner;
  Map<String, dynamic> expense = {
    'id': 'e' * 32,
    'employee_id': employeeId,
    'revision': 3,
    'status': 'approved',
    'purpose': 'Synthetischer Bahnbeleg',
    'total_minor': 4987,
    'submitted_by': worker,
    'items': [],
    'payments': [],
  };
  Map<String, dynamic>? withdrawal;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/me') return {'id': viewer};
    if (path.startsWith('/api/business/capabilities')) {
      final value = await super.call(path, body) as Map<String, dynamic>;
      return {
        ...value,
        'features': [
          ...value['features'],
          if (modernServer) 'personnel_expense_originals_v2',
        ],
        'permissions': [
          ...value['permissions'],
          if (approve) 'personnel.approve',
        ],
      };
    }
    if (path.startsWith('/api/business/personnel/expenses?')) {
      return {
        'employee_id': employeeId,
        'items': [copy(expense)],
      };
    }
    if (path.endsWith('/withdraw-approval')) {
      commands.add(copy(body!));
      if (!approve) throw const ApiException(403, 'Prüfrecht entzogen');
      accepted ??= copy(body);
      expect(body, accepted);
      withdrawal ??= {
        ...expense,
        'revision': 4,
        'status': 'rejected',
        'decision': {'reason': body['reason'], 'by': owner},
      };
      expense = copy(withdrawal!);
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      return copy(withdrawal!);
    }
    return super.call(path, body);
  }
}

void main() {
  Future<BusinessSession> show(
    WidgetTester tester,
    PersonnelApi api, {
    Uint8List? bytes,
  }) async {
    tester.view.physicalSize = const Size(1500, 1600);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(api: api);
    await session.load();
    await tester.pumpWidget(
      MaterialApp(
        home: BusinessPersonnelWorkflowPage(
          session: session,
          pickFile: () async => XFile.fromData(
            bytes ?? png,
            name: 'Vertrag.png',
            mimeType: 'image/png',
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    return session;
  }

  testWidgets(
    'approval withdrawal retains exact command across lost ACK and fresh permission revocation',
    (tester) async {
      final api = ExpenseApprovalApi(), session = await show(tester, api);
      try {
        await tester.ensureVisible(find.text('Freigabe zurücknehmen'));
        await tester.tap(find.text('Freigabe zurücknehmen'));
        await tester.pumpAndSettle();
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Prüfvermerk'),
          'Doppeltes Original vor Zahlung geprüft',
        );
        await tester.tap(find.text('Freigabe zurücknehmen').last);
        await tester.pumpAndSettle();
        expect(find.text('Erfolgsantwort verloren'), findsOneWidget);
        await tester.tap(find.text('Schließen'));
        await tester.pumpAndSettle();
        api.approve = false;
        api.generation++;
        await session.load();
        await tester.pumpAndSettle();
        await tester.tap(find.text('Unverändert wiederholen'));
        await tester.pumpAndSettle();
        expect(api.commands, hasLength(2));
        expect(find.text('Prüfrecht entzogen'), findsOneWidget);
        expect(
          session.pending('personnel-${'e' * 32}-withdraw-approval-3'),
          isTrue,
        );
        expect(api.withdrawal!['payments'], isEmpty);
        api.approve = true;
        api.generation++;
        await session.load();
        await tester.pumpAndSettle();
        await tester.tap(find.text('Unverändert wiederholen'));
        await tester.pumpAndSettle();
        expect(api.commands, hasLength(3));
        expect(api.commands[0], api.commands[1]);
        expect(api.commands[0], api.commands[2]);
        expect(api.commands[0]['revision'], 3);
        expect(find.text('Freigabe zurücknehmen'), findsNothing);
        expect(
          session.pending('personnel-${'e' * 32}-withdraw-approval-3'),
          isFalse,
        );
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );

  testWidgets(
    'employee cannot withdraw own approval even with reviewer permission',
    (tester) async {
      final api = ExpenseApprovalApi()..viewer = worker,
          session = await show(tester, api);
      try {
        expect(find.text('Freigabe zurücknehmen'), findsNothing);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );

  testWidgets('old server hides unavailable withdrawal action', (tester) async {
    final api = ExpenseApprovalApi()..modernServer = false,
        session = await show(tester, api);
    try {
      expect(find.text('Freigabe zurücknehmen'), findsNothing);
    } finally {
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    }
  }, variant: TargetPlatformVariant.only(TargetPlatform.windows));

  test('cent conversion preserves exact monetary inputs', () {
    expect(personnelMinor('49,87'), 4987);
    expect(personnelMinor('0.01'), 1);
    expect(personnelMinor('3500'), 350000);
    expect(personnelMinor('10000000000'), 1000000000000);
  });
  test('fractional cents, signs, exponent, zero and overflow are rejected', () {
    for (final value in ['1.001', '-1', '1e2', '0', '10000000000.01', '']) {
      expect(() => personnelMinor(value), throwsFormatException);
    }
  });
  test('multi-line actual expenses retain each original and whitelist submitted fields', () {
    final source = [
          {
            'date': '2026-10-28',
            'description': 'Vorgebuchte Bahn',
            'amount': '49,87',
            'receipt_file_id': fileId,
            'project_id': owner,
            'tax_rate': '19',
          },
          {
            'date': '2026-11-03',
            'description': 'Hotel',
            'amount': '100',
            'receipt_file_id': worker,
          },
        ],
        result = personnelExpenseValues(employeeId, {
          'purpose': 'Kundenreise',
          'start_date': '2026-11-02',
          'end_date': '2026-11-03',
        }, source);
    expect(result['revision'], 0);
    expect(result['items'][0]['amount_minor'], 4987);
    expect(result['items'][0]['date'], '2026-10-28');
    expect(result['items'][0].containsKey('tax_rate'), isFalse);
    expect(source[0]['amount'], '49,87');
    expect(result.containsKey('allowance'), isFalse);
  });
  test('corrections require reasons and preserve previous identity', () {
    final old = {'id': owner, 'revision': 6};
    expect(
      () => personnelExpenseValues(employeeId, {}, [
        {'amount': '1'},
      ], previous: old),
      throwsFormatException,
    );
    final result = personnelExpenseValues(
      employeeId,
      {'correction_reason': 'Original erneut geprüft'},
      [
        {'amount': '1'},
      ],
      previous: old,
    );
    expect(result['id'], owner);
    expect(result['revision'], 6);
  });
  test('month requires explicit completeness and exact employee/source', () {
    expect(
      personnelCloseValues(employeeId, preview(), {
        'completeness_confirmed': true,
      })['source_hash'],
      'a' * 64,
    );
    expect(
      () => personnelCloseValues(employeeId, preview(), {
        'completeness_confirmed': false,
      }),
      throwsFormatException,
    );
    expect(
      () => personnelCloseValues(owner, preview(), {
        'completeness_confirmed': true,
      }),
      throwsFormatException,
    );
  });
  test('month correction cannot change frozen period or omit reason', () {
    final old = {
      'id': owner,
      'employee_id': employeeId,
      'month': '2026-11',
      'revision': 2,
    };
    final values = {
      'completeness_confirmed': true,
      'correction_reason': 'Vertragsquelle korrigiert',
    };
    expect(
      personnelCloseValues(
        employeeId,
        preview(),
        values,
        previous: old,
      )['revision'],
      2,
    );
    expect(
      () => personnelCloseValues(
        employeeId,
        preview(),
        values,
        previous: {...old, 'month': '2026-10'},
      ),
      throwsFormatException,
    );
  });

  testWidgets(
    'private upload lost ACK survives close, fresh denied rights and changed generation with exact retry',
    (tester) async {
      final api = PersonnelApi(), session = await show(tester, api);
      try {
        await tester.tap(find.text('Personaloriginal hochladen'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Original unverändert speichern').last);
        await tester.pumpAndSettle();
        expect(find.text('Erfolgsantwort verloren'), findsOneWidget);
        expect(api.created, 1);
        await tester.tap(find.text('Schließen'));
        await tester.pumpAndSettle();
        expect(find.text('Unverändert wiederholen'), findsOneWidget);
        api.write = false;
        api.generation = 2;
        await session.load();
        await tester.pumpAndSettle();
        await tester.tap(find.text('Unverändert wiederholen'));
        await tester.pumpAndSettle();
        expect(find.text('Personalrecht entzogen'), findsOneWidget);
        expect(
          session.pending('personnel-file-$employeeId-personnel-new'),
          isTrue,
        );
        api.write = true;
        api.generation = 3;
        await session.load();
        await tester.pumpAndSettle();
        await tester.tap(find.text('Unverändert wiederholen'));
        await tester.pumpAndSettle();
        expect(api.created, 1);
        expect(api.commands, hasLength(3));
        expect(api.commands[0], api.commands[2]);
        expect(api.commands[0]['owner_visible'], isFalse);
        expect(base64Decode(api.commands[0]['content_base64']), png);
        expect(
          session.pending('personnel-file-$employeeId-personnel-new'),
          isFalse,
        );
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets('600 kB upload bound prevents sending oversized original', (
    tester,
  ) async {
    final api = PersonnelApi(),
        session = await show(tester, api, bytes: Uint8List(600001));
    try {
      await tester.tap(find.text('Personaloriginal hochladen'));
      await tester.pumpAndSettle();
      expect(
        find.text('Ein PDF-, PNG- oder JPEG-Original bis 600 kB auswählen.'),
        findsOneWidget,
      );
      expect(api.commands, isEmpty);
    } finally {
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
      api.dispose();
    }
  }, variant: TargetPlatformVariant.only(TargetPlatform.windows));
  testWidgets(
    'known personnel read revocation removes other employee and private filenames',
    (tester) async {
      final api = PersonnelApi()..created = 1,
          session = await show(tester, api);
      try {
        expect(find.text('Vertrag.png'), findsOneWidget);
        api.read = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text('Vertrag.png'), findsNothing);
        expect(find.text('Synthetischer Mitarbeiter'), findsNothing);
        expect(find.text('Personaloriginal hochladen'), findsNothing);
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
}

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_migrations.dart';
import 'package:smartplan_office/business_session.dart';

const packageId = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    fileId = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
final sha = 'c' * 64, reportSha = 'd' * 64;
final declaration = {
  'source_system': 'hero',
  'source_account': 'synthetic-account',
  'label': 'Synthetischer Import',
  'period_from': null,
  'period_to': null,
  'scope': 'Ausgewählte Testquellen',
};
final table = {
  'file_id': fileId,
  'kind': 'contact',
  'format': 'csv',
  'encoding': 'utf-8-sig',
  'delimiter': ';',
  'decimal_separator': ',',
  'columns': {'source_id': 'Kennung', 'name': 'Name'},
};
Map<String, dynamic> record({String status = 'staged', int revision = 1}) => {
  'id': packageId,
  ...declaration,
  'status': status,
  'files': [],
  'mapping': {
    'revision': revision,
    'tables': [table],
    'decisions': [],
  },
  'report': status == 'staged' ? null : report(),
  'reconciliation': status == 'reconciled'
      ? {'note': 'Originale abgeglichen'}
      : null,
};
Map<String, dynamic> preview() => {
  'package_id': packageId,
  'revision': 1,
  'ready': true,
  'preview_sha256': sha,
  'rows': [
    {
      'kind': 'contact',
      'source_id': 'old-customer-1',
      'file_id': fileId,
      'row': 1,
      'values': {'name': 'Synthetischer neuer Kunde'},
      'action': 'create',
      'source_sha256': sha,
      'errors': [],
      'candidates': [],
      'reason': '',
    },
  ],
  'counts': {
    'source': 1,
    'create': 1,
    'link': 0,
    'reuse': 0,
    'skip': 0,
    'errors': 0,
  },
  'totals': [],
  'errors': [],
};
Map<String, dynamic> report() => {
  ...preview(),
  'report_sha256': reportSha,
  'financial_effects': false,
};

class MigrationApi extends OfficeApi {
  MigrationApi() : super(apiVersion: 'v1') {
    token = 'synthetic-import-test-token';
  }
  bool allowed = true, owner = true, lose = false;
  int generation = 1;
  String status = 'staged';
  final commands = <Map<String, dynamic>>[], paths = <String>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    paths.add(path);
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': generation,
        'readonly': false,
        'features': ['file_migrations'],
        'capabilities': ['business_migrations'],
        'permissions': allowed
            ? [
                'settings.manage',
                'contacts.read',
                'finance.read',
                'documents.read',
                'contacts.write',
                'projects.manage',
              ]
            : [],
      };
    if (path == '/api/me') return {'role': owner ? 'owner' : 'manager'};
    if (path == '/api/business/migrations/options')
      return {
        'fields': {
          'contact': ['source_id', 'name'],
        },
        'required_fields': {
          'contact': ['source_id', 'name'],
        },
        'contacts': [],
        'projects': [],
        'max_file_bytes': 2097152,
      };
    if (path == '/api/business/migrations')
      return {
        'items': [record(status: status)],
      };
    if (path == '/api/business/migrations/$packageId')
      return record(status: status);
    if (path.endsWith('/preview')) return preview();
    if (path.endsWith('/report')) return report();
    if (path.endsWith('/apply')) {
      commands.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
      status = 'applied';
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Erfolgsantwort verloren');
      }
      return report();
    }
    if (path.endsWith('/reconcile')) {
      commands.add(jsonDecode(jsonEncode(body)) as Map<String, dynamic>);
      status = 'reconciled';
      return {
        'package_id': packageId,
        'report_sha256': reportSha,
        'note': body!['note'],
      };
    }
    throw StateError(path);
  }
}

void main() {
  test('explicit declaration validates paired dates and exact cents preserve missing values', () {
    expect(
      migrationDeclaration({...declaration, 'period_from': ''})['period_from'],
      isNull,
    );
    expect(
      () => migrationDeclaration({...declaration, 'source_account': ''}),
      throwsFormatException,
    );
    expect(
      () => migrationDeclaration({...declaration, 'period_from': '2026-01-01'}),
      throwsFormatException,
    );
    expect(migrationAmount(123456789012345), '1234567890123,45');
    expect(migrationAmount(-1), '-0,01');
    expect(migrationAmount(null), 'Nicht angegeben');
    expect(
      migrationAmount(1000000000000000000, '10000000000000000.01'),
      '10000000000000000,01',
    );
  });
  test('duplicate decisions cannot link historical documents or mutate prior mapping', () {
    final source = record(),
        result = migrationMapping(
          source,
          decision: {
            'kind': 'contact',
            'source_id': 'legacy-1',
            'action': 'link',
            'target_id': fileId,
            'reason': 'Anschrift und Quelle geprüft',
          },
        );
    expect(result['revision'], 1);
    expect((source['mapping']['decisions'] as List), isEmpty);
    expect(
      () => migrationMapping(
        source,
        decision: {
          'kind': 'document',
          'source_id': 'old-invoice',
          'action': 'link',
          'target_id': fileId,
          'reason': 'Falsch',
        },
      ),
      throwsFormatException,
    );
  });
  test('apply and acknowledgement bind current package, preview, revision and neutral financial effects', () {
    final body = migrationApplyValues(record(), preview(), true);
    expect(body['preview_sha256'], sha);
    expect(
      () =>
          migrationApplyValues(record(), {...preview(), 'ready': false}, true),
      throwsFormatException,
    );
    expect(
      () => migrationApplyValues(record(), {
        ...preview(),
        'package_id': fileId,
      }, true),
      throwsFormatException,
    );
    expect(
      migrationReceipt(
        '/migrations/$packageId/apply',
        body,
        report(),
      )['financial_effects'],
      false,
    );
    expect(
      () => migrationReceipt('/migrations/$packageId/apply', body, {
        ...report(),
        'financial_effects': true,
      }),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => migrationReceipt('/migrations/$packageId/apply', body, {
        ...report(),
        'preview_sha256': reportSha,
      }),
      throwsA(isA<ApiException>()),
    );
  });
  test('pending accepted apply survives rights and owner loss and exact nonce confirms once', () async {
    final api = MigrationApi()..lose = true,
        session = BusinessSession(api: api);
    addTearDown(session.dispose);
    addTearDown(api.dispose);
    await session.load();
    const key = 'migration-apply-test';
    final body = migrationApplyValues(record(), preview(), true);
    await expectLater(
      session.command(
        key,
        '/migrations/$packageId/apply',
        body,
        validateResult: (value) =>
            migrationReceipt('/migrations/$packageId/apply', body, value),
      ),
      throwsA(isA<ApiException>()),
    );
    final original = Map.of(api.commands.single);
    api.allowed = false;
    await expectLater(
      session.repeatMigrationCommand(key),
      throwsA(isA<ApiException>()),
    );
    expect(session.pending(key), true);
    expect(api.commands.length, 1);
    api.allowed = true;
    api.owner = false;
    await expectLater(
      session.repeatMigrationCommand(key),
      throwsA(isA<ApiException>()),
    );
    expect(api.commands.length, 1);
    api.owner = true;
    await session.repeatMigrationCommand(key);
    expect(api.commands.last, original);
    expect(session.pending(key), false);
  });
  Future<BusinessSession> show(WidgetTester tester, MigrationApi api) async {
    tester.view.physicalSize = const Size(1300, 2200);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = BusinessSession(api: api);
    await session.load();
    await tester.pumpWidget(
      MaterialApp(home: BusinessMigrationsPage(session: session)),
    );
    await tester.pumpAndSettle();
    return session;
  }

  testWidgets(
    'native preview requires confirmation, lost reply stays locked, report and reconciliation remain separate',
    (tester) async {
      final api = MigrationApi()..lose = true,
          session = await show(tester, api);
      try {
        await tester.tap(find.text('Synthetischer Import'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('3 · Übernahmevorschau prüfen'));
        await tester.pumpAndSettle();
        await tester.ensureVisible(find.text('Geprüfte Vorschau übernehmen'));
        await tester.tap(find.text('Geprüfte Vorschau übernehmen'));
        await tester.pumpAndSettle();
        final confirm = find.text(
          'Ich habe Quellen, Dubletten, Beziehungen und Beträge geprüft und bestätige genau diese Vorschau.',
        );
        await tester.tap(confirm);
        await tester.pump();
        await tester.tap(
          find.widgetWithText(
            FilledButton,
            'Geprüfte Daten einmalig übernehmen',
          ),
        );
        await tester.pumpAndSettle();
        expect(api.commands.length, 1);
        expect(find.textContaining('noch unbestätigt'), findsOneWidget);
        await tester.tap(find.widgetWithText(FilledButton, 'Erneut senden'));
        await tester.pumpAndSettle();
        expect(api.commands.length, 2);
        expect(api.commands[0], api.commands[1]);
        expect(api.status, 'applied');
        final reconcile = find.text(
          'Abgleich des deklarierten Umfangs bestätigen',
        );
        await tester.ensureVisible(reconcile);
        await tester.tap(reconcile);
        await tester.pumpAndSettle();
        await tester.enterText(
          find.widgetWithText(
            TextFormField,
            'Abgleichvermerk und verbleibende Lücken',
          ),
          'Originale abgeglichen',
        );
        await tester.tap(
          find.text(
            'Ich bestätige den Abgleich dieses deklarierten Exportumfangs mit den Originalen.',
          ),
        );
        await tester.pump();
        await tester.tap(
          find.widgetWithText(
            FilledButton,
            'Abgleich unveränderlich festhalten',
          ),
        );
        await tester.pumpAndSettle();
        expect(api.status, 'reconciled');
        expect(api.commands.last['report_sha256'], reportSha);
        expect(
          api.paths.where(
            (path) =>
                path.contains('/documents') || path.contains('/accounting'),
          ),
          isEmpty,
        );
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
  testWidgets(
    'revoked global source rights clear loaded package and prevent new import commands',
    (tester) async {
      final api = MigrationApi(), session = await show(tester, api);
      try {
        expect(find.text('Synthetischer Import'), findsOneWidget);
        api.allowed = false;
        await session.load();
        await tester.pumpAndSettle();
        expect(find.text('Synthetischer Import'), findsNothing);
        expect(find.text('Importpaket anlegen'), findsNothing);
        expect(api.commands, isEmpty);
      } finally {
        await tester.pumpWidget(const SizedBox());
        session.dispose();
        api.dispose();
      }
    },
    variant: TargetPlatformVariant.only(TargetPlatform.windows),
  );
}

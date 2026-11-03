import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_purchase_changes.dart';

final fixture = Map<String, dynamic>.from(
  jsonDecode(File('test/fixtures/purchase_changes.json').readAsStringSync()),
);
Map<String, dynamic> clone(Object? value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)));
Object? redact(Object? value) {
  if (value is List) return value.map(redact).toList();
  if (value is Map)
    return {
      for (final entry in value.entries)
        if (!'${entry.key}'.endsWith('_net'))
          entry.key: entry.key == 'financial_values_visible'
              ? false
              : redact(entry.value),
    };
  return value;
}

Map<String, dynamic> command() => {
  ...clone(fixture['body']),
  'preview_sha256': fixture['preview']['preview_sha256'],
  'confirmation': true,
};

class PurchaseChangesApi extends OfficeApi {
  PurchaseChangesApi() : super(apiVersion: 'v1') {
    token = 'synthetic-purchase-changes-token';
  }
  bool allowed = true, financial = true, enabled = true, lose = false;
  final posts = <Map<String, dynamic>>[],
      reads = <String>[],
      effects = <String>{};
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    reads.add(path);
    final id = fixture['detail']['id'];
    if (path.startsWith('/api/business/capabilities'))
      return {
        'compatibility_mode': 'business',
        'generation': 1,
        'readonly': false,
        'features': ['purchase_changes', 'organization_modules'],
        'capabilities': ['business_purchase_changes'],
        'permissions': allowed
            ? [
                'inventory.read',
                'inventory.write',
                'finance.approve',
                'finance.write',
                if (financial) 'finance.read',
              ]
            : [],
        'organization': {
          'revision': 1,
          'configured': true,
          'modules': {
            for (final section in BusinessSession.organizationSections)
              section: {'enabled': enabled, 'visible': true},
          },
        },
      };
    if (path == '/api/business/purchasing/orders/$id/changes') {
      final value = clone(
        financial ? fixture['detail'] : redact(fixture['detail']),
      );
      value['return_revision'] = effects.isEmpty ? 0 : 1;
      return value;
    }
    if (path ==
        '/api/business/purchasing/orders/$id/supplier-returns/preview') {
      expect(body, fixture['body']);
      return clone(financial ? fixture['preview'] : redact(fixture['preview']));
    }
    if (path == '/api/business/purchasing/orders/$id/supplier-returns') {
      posts.add(clone(body));
      effects.add(body!['request_id']);
      if (lose) {
        lose = false;
        throw const ApiException(0, 'Angenommene Antwort verloren.');
      }
      return clone(financial ? fixture['receipt'] : redact(fixture['receipt']));
    }
    throw StateError(path);
  }
}

void main() {
  test('exact decimal quantities never round or invent a null return', () {
    expect(purchaseChangeQuantity('0002,1'), '2.1000');
    expect(
      purchaseChangeQuantity('9007199254740992.0001'),
      '9007199254740992.0001',
    );
    for (final value in [null, '', '-1', '1.00001', '1e2']) {
      expect(() => purchaseChangeQuantity(value), throwsFormatException);
    }
    expect(
      () => purchaseChangeQuantity('0', positive: true),
      throwsFormatException,
    );
  });
  test(
    'input binds actual receipt source and amendment includes every position',
    () {
      final detail = clone(fixture['detail']),
          body = clone(fixture['body']),
          values = {
            ...body,
            'quantity_${detail['receipts'][0]['id']}_0': '2,0000',
          };
      expect(purchaseChangeInput(detail, 'supplier-returns', values), body);
      final amendment = purchaseChangeInput(detail, 'amendments', {
        ...values,
        'kind': 'replacement',
        'effective_on': '2026-11-03',
        'quantity_0': '12',
      });
      expect(amendment['lines'], [
        {'line_index': 0, 'authorized_quantity': '12.0000'},
      ]);
      expect(
        () => purchaseChangeBasis({...detail, 'order_id': 'b' * 32}),
        throwsFormatException,
      );
    },
  );
  test('strict previews and receipts preserve source, exact quantities and price redaction', () {
    final detail = clone(fixture['detail']),
        body = clone(fixture['body']),
        preview = clone(fixture['preview']);
    purchaseChangePreview(detail, 'supplier-returns', body, preview);
    purchaseChangeReceipt(
      detail['id'],
      'supplier-returns',
      command(),
      preview,
      fixture['receipt'],
    );
    purchaseChangeReceipt(
      detail['id'],
      'supplier-returns',
      command(),
      preview,
      redact(fixture['receipt']),
    );
    final bad = clone(fixture['receipt']);
    bad['record']['lines'][0]['quantity'] = '3.0000';
    expect(
      () => purchaseChangeReceipt(
        detail['id'],
        'supplier-returns',
        command(),
        preview,
        bad,
      ),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => purchaseChangePreview(detail, 'supplier-returns', body, {
        ...preview,
        'values': {...body, 'reason': 'Other'},
      }),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => purchaseChangeReceipt(
        detail['id'],
        'supplier-returns',
        command(),
        preview,
        {...clone(fixture['receipt']), 'financial_values_visible': false},
      ),
      throwsA(isA<ApiException>()),
    );
  });
  for (final scoped in [false, true])
    test(
      'lost ACK retries original nonce after fresh project rights and source advance (scoped=$scoped)',
      () async {
        final api = PurchaseChangesApi()..lose = true,
            session = BusinessSession(
              api: api,
              projectId: scoped ? fixture['detail']['project_id'] : null,
            );
        await session.load();
        final id = fixture['detail']['id'],
            key = 'purchase-change-supplier-returns-$id',
            path = '/purchasing/orders/$id/supplier-returns',
            body = command();
        await expectLater(
          session.command(
            key,
            path,
            body,
            validateResult: (value) => purchaseChangeReceipt(
              id,
              'supplier-returns',
              body,
              clone(fixture['preview']),
              value,
            ),
          ),
          throwsA(isA<ApiException>()),
        );
        api.allowed = false;
        await expectLater(
          session.repeatPurchaseChangeCommand(key),
          throwsA(isA<ApiException>()),
        );
        expect(session.pending(key), true);
        api.allowed = true;
        api.financial = false;
        api.enabled = false;
        await session.repeatPurchaseChangeCommand(key);
        expect(api.posts[0], api.posts[1]);
        expect(api.effects.length, 1);
        expect(session.pending(key), false);
        expect(
          api.reads.any(
            (path) =>
                path.endsWith('project_id=${fixture['detail']['project_id']}'),
          ),
          true,
        );
        session.dispose();
        api.dispose();
      },
    );
  testWidgets(
    'real return form leads to source-bound preview and explicit confirmation without duplicate effect after lost ACK',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1200, 1200));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final api = PurchaseChangesApi()..lose = true,
          session = BusinessSession(api: api);
      await session.load();
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessPurchaseChangesPage(
            session: session,
            orderId: fixture['detail']['id'],
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(
        find.widgetWithText(
          OutlinedButton,
          'Tatsächliche Lieferantenretoure vorbereiten',
        ),
      );
      await tester.pumpAndSettle();
      Future<void> fill(String name, String value) async {
        final finder = find.byKey(ValueKey('business-field-$name'));
        await tester.ensureVisible(finder);
        await tester.enterText(finder, value);
      }

      await fill('reference', 'RET-SYN');
      await fill('returned_on', '2026-11-03');
      await fill('reason', 'Tatsächliche belegte Rücksendung.');
      final evidence = find.byWidgetPredicate(
        (widget) =>
            widget is DropdownButtonFormField<String> &&
            widget.decoration.labelText ==
                'Unveränderliches Original dieser Bestellung',
      );
      await tester.ensureVisible(evidence);
      await tester.tap(evidence);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Original.pdf').last);
      await tester.pumpAndSettle();
      await fill('quantity_${fixture['detail']['receipts'][0]['id']}_0', '2');
      await tester.ensureVisible(
        find.widgetWithText(FilledButton, 'Aktuelle Mengen und Quellen prüfen'),
      );
      await tester.tap(
        find.widgetWithText(FilledButton, 'Aktuelle Mengen und Quellen prüfen'),
      );
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Auszubuchender Lagerwert netto: 20,0000 EUR'),
        findsOneWidget,
      );
      await tester.ensureVisible(find.byType(SwitchListTile));
      await tester.tap(find.byType(SwitchListTile));
      await tester.pumpAndSettle();
      await tester.tap(
        find.widgetWithText(
          FilledButton,
          'Physische Rücksendung verbindlich buchen',
        ),
      );
      await tester.pumpAndSettle();
      expect(api.posts.length, 1);
      await tester.tap(
        find.widgetWithText(
          FilledButton,
          'Ursprüngliche Antwort erneut prüfen',
        ),
      );
      await tester.pumpAndSettle();
      expect(api.effects.length, 1);
      expect(api.posts[0], api.posts[1]);
      await tester.pumpWidget(const SizedBox());
      session.dispose();
      api.dispose();
    },
  );
}

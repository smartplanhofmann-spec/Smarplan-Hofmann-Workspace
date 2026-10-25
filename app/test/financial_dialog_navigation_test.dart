import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_shell.dart';
import 'package:smartplan_office/design.dart';

import 'business_session_test.dart' show BusinessTestApi;

const _project = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
const _document = 'dddddddddddddddddddddddddddddddd';
const _cancellation = 'cccccccccccccccccccccccccccccccc';

class FinancialNavigationApi extends BusinessTestApi {
  final permissions = <String>{
    'finance.read',
    'finance.write',
    'finance.issue',
    'finance.approve',
    'documents.read',
    'documents.write',
    'documents.classify',
  };
  bool finalDocument = false, emptyFinance = false, emptyAccess = false;
  bool failFinance = false, failAccess = false, failDocument = false;
  bool failPayment = false;
  bool denyGlobalOutbox = false, populatedOutbox = false;
  int? financeDenied;
  Map<String, dynamic>? updatedCreditNote;
  String documentKind = 'invoice';

  Map<String, dynamic> document([String id = _document]) => {
    'id': id,
    'project_id': _project,
    'kind': id == _cancellation ? 'credit_note' : documentKind,
    'title': id == _cancellation
        ? 'Storno zur Navigation'
        : 'Rechnung zur Navigation',
    'status': id == _cancellation || !finalDocument ? 'draft' : 'final',
    'number': finalDocument ? 'RE-NAV-001' : null,
    'revision': 1,
    'issue_date': '2026-10-25',
    if (id == _cancellation) ...{
      'cancels': _document,
      'cancelled_number': 'RE-NAV-001',
      'cancel_reason': 'Ursprünglicher Stornogrund',
      'buyer': {'name': 'Empfänger der Originalrechnung', 'city': 'Quellstadt'},
      ...?updatedCreditNote,
    },
    'positions': [
      {
        'description': 'Vertrauliche Montage',
        'quantity': id == _cancellation ? '2.5000' : '2',
        'unit': 'HUR',
        'unit_price_net': '50.00',
        'tax_rate': id == _cancellation ? '19.00' : '19',
        'kind': 'labor',
      },
    ],
    'totals': {'net': '100.00', 'tax': '19.00', 'gross': '119.00'},
  };

  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    calls.add((path: path, body: body == null ? null : Map.of(body)));
    final route = path.split('?').first;
    if (route == '/api/business/capabilities') {
      return {
        'storage_version': 7,
        'compatibility_mode': 'business',
        'readonly': false,
        'generation': 1,
        'capabilities': [
          'business_foundation',
          'business_documents',
          'business_finance',
        ],
        'permissions': permissions.toList(),
      };
    }
    if (route == '/api/business/templates' ||
        route == '/api/business/documents/time-sources')
      return {'items': []};
    if (route == '/api/business/documents')
      return {
        'items': [document()],
      };
    if (route == '/api/business/documents/$_document' ||
        route == '/api/business/documents/$_cancellation') {
      if (route.endsWith(_cancellation) && body != null) {
        const allowed = {
          'request_id',
          'revision',
          'title',
          'issue_date',
          'due_date',
          'notes',
          'intro',
          'cancel_reason',
        };
        if (body.keys.any((key) => !allowed.contains(key)))
          throw const ApiException(
            409,
            'Vollstorno muss die Originalrechnung unverändert umkehren',
          );
        updatedCreditNote = Map.of(body);
      }
      if (failDocument)
        throw const ApiException(503, 'Archiv vorübergehend nicht erreichbar');
      return document(
        route.endsWith(_cancellation) ? _cancellation : _document,
      );
    }
    if (route.endsWith('/cancel')) return document(_cancellation);
    if (route.endsWith('/signatures')) return {'items': []};
    if (route.endsWith('/finalize')) {
      finalDocument = true;
      return document();
    }
    if (route.endsWith('/email-preview')) {
      return {
        'recipient': 'navigation@example.test',
        'subject': 'Rechnung prüfen',
        'text': 'Vertraulicher Rechnungstext',
        'attachments': [],
        'preview_sha256': 'a' * 64,
      };
    }
    if (route.endsWith('/email')) return {'status': 'queued'};
    if (route == '/api/business/finance/open-items') {
      if (financeDenied != null)
        throw ApiException(
          financeDenied!,
          'Projektfinanzen nicht mehr verfügbar',
        );
      if (failFinance)
        throw const ApiException(
          503,
          'Finanzen vorübergehend nicht erreichbar',
        );
      return {
        'items': emptyFinance
            ? []
            : [
                {
                  'id': _document,
                  'document_id': _document,
                  'number': 'RE-NAV-001',
                  'open': '75.00',
                  'paid': '25.00',
                  'due_date': '2026-10-01',
                },
              ],
      };
    }
    if (route == '/api/business/finance/outbox') {
      if (denyGlobalOutbox)
        throw const ApiException(403, 'Globale Finanzen nicht freigegeben');
      return {
        'items': populatedOutbox
            ? [
                {'recipient': 'global@example.test', 'status': 'pending'},
              ]
            : [],
      };
    }
    if (route == '/api/business/finance/payments') {
      if (failPayment)
        throw const ApiException(400, 'Buchungshinweis bitte prüfen');
      return {'id': 'p' * 32};
    }
    if (route == '/api/business/finance/dunning/preview') {
      return {
        'items': [
          {
            'id': 'e' * 32,
            'number': 'RE-NAV-001',
            'recipient': 'navigation@example.test',
            'open': '75.00',
            'total': '75.00',
            'rule': {'name': 'Erinnerung', 'text': 'Bitte prüfen.'},
          },
        ],
      };
    }
    if (route.endsWith('/approve')) return {'sent': false};
    if (route == '/api/projects/$_project/links') {
      if (failAccess)
        throw const ApiException(
          503,
          'Freigaben vorübergehend nicht erreichbar',
        );
      return emptyAccess
          ? []
          : [
              {
                'id': 'a' * 32,
                'title': 'Unterlage zur Navigation',
                'url': 'https://example.test/navigation',
                'category': 'document',
                'revision': 1,
              },
            ];
    }
    if (route == '/api/projects/$_project/mail-attachments')
      return {'files': []};
    if (route.endsWith('/classification')) {
      return {
        'id': 'a' * 32,
        'kind': 'link',
        'classification': 'restricted',
        'revision': 0,
        'source_fingerprint': 'a' * 64,
      };
    }
    throw StateError('Unexpected navigation request: $path');
  }
}

final _sessions = <BusinessSession>[];
final _apis = <FinancialNavigationApi>[];

void financialWidgets(
  String description,
  Future<void> Function(WidgetTester) body,
) {
  testWidgets(description, (tester) async {
    try {
      await body(tester);
    } finally {
      await tester.pumpWidget(const SizedBox());
      for (final session in _sessions) session.dispose();
      for (final api in _apis) api.dispose();
      _sessions.clear();
      _apis.clear();
    }
  });
}

Future<BusinessSession> showFeature(
  WidgetTester tester,
  FinancialNavigationApi api,
  String feature, {
  String? projectId = _project,
}) async {
  tester.view.physicalSize = const Size(1100, 1200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final session = BusinessSession(api: api, projectId: projectId);
  await session.load();
  await tester.pumpWidget(
    MaterialApp(
      theme: officeTheme(),
      home: Scaffold(
        body: BusinessProjectFeature(session: session, feature: feature),
      ),
    ),
  );
  await tester.pumpAndSettle();
  _sessions.add(session);
  _apis.add(api);
  return session;
}

Future<void> tapText(
  WidgetTester tester,
  String label, {
  bool settle = true,
}) async {
  final target = find.text(label).last;
  await tester.ensureVisible(target);
  await tester.tap(target);
  if (settle) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump(const Duration(milliseconds: 400));
  }
}

Future<void> openDocument(WidgetTester tester) async {
  await tapText(tester, 'Rechnung zur Navigation');
}

Future<void> openManualPosition(WidgetTester tester) async {
  await openDocument(tester);
  await tapText(tester, 'Entwurf bearbeiten');
  await tapText(tester, 'Vertrauliche Montage');
}

Finder saveButton() => find.widgetWithText(FilledButton, 'Speichern');

void main() {
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });

  financialWidgets(
    'Credit-note metadata uses German dates and numbers and saves valid edited dates as ISO',
    (tester) async {
      final api = FinancialNavigationApi()..finalDocument = true;
      await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'Stornoentwurf erstellen');
      await tester.enterText(
        find.byKey(const ValueKey('business-field-reason')),
        'Korrektur zur Navigation',
      );
      await tapText(tester, 'Speichern');
      await tapText(tester, 'Entwurf bearbeiten');
      final issue = find.byType(TextFormField).at(1);
      final due = find.byType(TextFormField).at(2);
      expect(
        tester.widget<TextFormField>(issue).controller!.text,
        '25.10.2026',
      );
      expect(find.text('Belegdatum (TT.MM.JJJJ)'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Vertrauliche Montage'),
        300,
        scrollable: find.byType(Scrollable).last,
      );
      expect(find.textContaining('2,5000 HUR'), findsOneWidget);
      expect(find.textContaining('19,00 %'), findsOneWidget);
      await tester.enterText(issue, '31.02.2028');
      await tester.enterText(due, '04.03.2028');
      await tapText(tester, 'Entwurf speichern');
      expect(api.updatedCreditNote, isNull);
      expect(find.text('Bitte gültiges Datum eingeben.'), findsOneWidget);
      await tester.enterText(issue, '29.02.2028');
      await tapText(tester, 'Entwurf speichern');
      expect(api.updatedCreditNote!['issue_date'], '2028-02-29');
      expect(api.updatedCreditNote!['due_date'], '2028-03-04');
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'A bound credit note saves edited metadata with exactly the canonical fields',
    (tester) async {
      final api = FinancialNavigationApi()..finalDocument = true;
      await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'Stornoentwurf erstellen');
      await tester.enterText(
        find.byKey(const ValueKey('business-field-reason')),
        'Korrektur zur Navigation',
      );
      await tapText(tester, 'Speichern');
      await tapText(tester, 'Entwurf bearbeiten');
      await tester.enterText(
        find.byKey(const ValueKey('business-document-title')),
        'Überarbeitete Stornogutschrift',
      );
      await tapText(tester, 'Entwurf speichern');
      expect(api.updatedCreditNote, isNotNull);
      expect(api.updatedCreditNote!.keys.toSet(), {
        'request_id',
        'revision',
        'title',
        'issue_date',
        'notes',
        'intro',
        'cancel_reason',
      });
      expect(api.updatedCreditNote!['title'], 'Überarbeitete Stornogutschrift');
      expect(find.text('Überarbeitete Stornogutschrift'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Credit-note source basis is readable and cannot be edited at phone width',
    (tester) async {
      final api = FinancialNavigationApi()..finalDocument = true;
      await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'Stornoentwurf erstellen');
      await tester.enterText(
        find.byKey(const ValueKey('business-field-reason')),
        'Korrektur zur Navigation',
      );
      await tapText(tester, 'Speichern');
      await tapText(tester, 'Entwurf bearbeiten');
      tester.view.physicalSize = const Size(390, 840);
      await tester.pumpAndSettle();
      expect(find.text('Position hinzufügen'), findsNothing);
      expect(find.byType(DropdownButtonFormField<String>), findsNothing);
      expect(find.byKey(const ValueKey('business-buyer-name')), findsNothing);
      expect(find.text('Empfänger der Originalrechnung'), findsOneWidget);
      final sourcePosition = find.text('Vertrauliche Montage');
      await tester.scrollUntilVisible(
        sourcePosition,
        300,
        scrollable: find.byType(Scrollable).last,
      );
      await tester.tap(sourcePosition);
      await tester.pumpAndSettle();
      expect(find.byType(AlertDialog), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pageBack();
      await tester.pumpAndSettle();
    },
  );

  for (final readLoss in [false, true]) {
    financialWidgets(
      'Credit-note metadata form respects fresh ${readLoss ? 'read' : 'write'} loss',
      (tester) async {
        final api = FinancialNavigationApi()..finalDocument = true;
        final session = await showFeature(tester, api, 'Belege');
        await openDocument(tester);
        await tapText(tester, 'Stornoentwurf erstellen');
        await tester.enterText(
          find.byKey(const ValueKey('business-field-reason')),
          'Korrektur zur Navigation',
        );
        await tapText(tester, 'Speichern');
        await tapText(tester, 'Entwurf bearbeiten');
        api.permissions.remove(readLoss ? 'finance.read' : 'finance.write');
        await session.load();
        await tester.pumpAndSettle();
        final title = find.byKey(const ValueKey('business-document-title'));
        if (readLoss) {
          expect(title, findsNothing);
          expect(find.text('Empfänger der Originalrechnung'), findsNothing);
        } else {
          expect(tester.widget<TextFormField>(title).enabled, isFalse);
          expect(
            tester
                .widget<FilledButton>(
                  find.widgetWithText(FilledButton, 'Entwurf speichern'),
                )
                .onPressed,
            isNull,
          );
        }
        expect(api.updatedCreditNote, isNull);
        await tester.pageBack();
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      },
    );
  }

  financialWidgets(
    'Project finance loads authorized open items without requesting global outbox',
    (tester) async {
      final api = FinancialNavigationApi()
        ..denyGlobalOutbox = true
        ..populatedOutbox = true;
      await showFeature(tester, api, 'Finanzen');
      expect(find.text('RE-NAV-001'), findsOneWidget);
      expect(
        api.calls.where((c) => c.path == '/api/business/finance/outbox'),
        isEmpty,
      );
      expect(find.text('Versandstand'), findsNothing);
      expect(find.text('global@example.test'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets('Global finance retains its authorized outbox area', (
    tester,
  ) async {
    final api = FinancialNavigationApi()..populatedOutbox = true;
    await showFeature(tester, api, 'Finanzen', projectId: null);
    expect(
      api.calls.where((c) => c.path == '/api/business/finance/outbox'),
      hasLength(1),
    );
    expect(find.text('Versandstand'), findsOneWidget);
    expect(find.text('global@example.test'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  for (final status in [403, 404]) {
    financialWidgets(
      'Fresh open-item $status clears previously displayed project financial rows',
      (tester) async {
        final api = FinancialNavigationApi();
        final session = await showFeature(tester, api, 'Finanzen');
        expect(find.text('RE-NAV-001'), findsOneWidget);
        api.financeDenied = status;
        final pending = tester
            .state<RefreshIndicatorState>(find.byType(RefreshIndicator))
            .show();
        await tester.pumpAndSettle();
        await pending;
        expect(find.text('RE-NAV-001'), findsNothing);
        expect(find.textContaining('75,00'), findsNothing);
        expect(
          find.textContaining('Projektfinanzen nicht mehr verfügbar'),
          findsOneWidget,
        );
        expect(session.can('finance.read'), isTrue);
        expect(tester.takeException(), isNull);
      },
    );
  }

  financialWidgets(
    'New document kinds exclude an unbound cancellation or credit note',
    (tester) async {
      final api = FinancialNavigationApi();
      await showFeature(tester, api, 'Belege');
      await tapText(tester, 'Beleg erstellen');
      await tester.tap(find.byType(DropdownButtonFormField<String>).first);
      await tester.pumpAndSettle();
      expect(find.text('Storno'), findsNothing);
      expect(find.text('Stornogutschrift'), findsNothing);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Rechnung zur Navigation'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  for (final kind in [
    'offer',
    'estimate',
    'order_confirmation',
    'delivery_note',
    'credit_note',
  ]) {
    financialWidgets('Final $kind does not offer an unsupported cancellation', (
      tester,
    ) async {
      final api = FinancialNavigationApi()
        ..finalDocument = true
        ..documentKind = kind;
      await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      expect(find.text('Stornoentwurf erstellen'), findsNothing);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }

  for (final kind in [
    'invoice',
    'advance_invoice',
    'cumulative_invoice',
    'final_invoice',
  ]) {
    financialWidgets('Final $kind retains its bound cancellation action', (
      tester,
    ) async {
      final api = FinancialNavigationApi()
        ..finalDocument = true
        ..documentKind = kind;
      await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      expect(find.text('Stornoentwurf erstellen'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }

  financialWidgets(
    'Invoice editor survives fresh write revocation and back navigation',
    (tester) async {
      final api = FinancialNavigationApi();
      final session = await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'Entwurf bearbeiten');
      api.permissions.remove('finance.write');
      await session.load();
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(
        find.byKey(const ValueKey('business-document-title')),
        findsOneWidget,
      );
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Entwurf speichern'),
            )
            .onPressed,
        isNull,
      );
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Rechnung zur Navigation'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  for (final readLoss in [false, true]) {
    financialWidgets(
      'Payment dialog respects fresh ${readLoss ? 'read' : 'write'} loss and closes cleanly',
      (tester) async {
        final api = FinancialNavigationApi();
        final session = await showFeature(tester, api, 'Finanzen');
        await tapText(tester, 'Zahlung erfassen');
        api.permissions.remove(readLoss ? 'finance.read' : 'finance.write');
        await session.load();
        await tester.pumpAndSettle();
        expect(tester.widget<FilledButton>(saveButton()).onPressed, isNull);
        if (readLoss) {
          expect(
            find.byKey(const ValueKey('business-field-amount')),
            findsNothing,
          );
        }
        expect(api.calls.where((c) => c.body != null), isEmpty);
        await tapText(tester, 'Schließen');
        expect(find.byType(AlertDialog), findsNothing);
        expect(tester.takeException(), isNull);
      },
    );

    financialWidgets(
      'Manual position dialog respects fresh ${readLoss ? 'read' : 'write'} loss and returns',
      (tester) async {
        final api = FinancialNavigationApi();
        final session = await showFeature(tester, api, 'Belege');
        await openManualPosition(tester);
        api.permissions.remove(readLoss ? 'finance.read' : 'finance.write');
        await session.load();
        await tester.pumpAndSettle();
        expect(tester.widget<FilledButton>(saveButton()).onPressed, isNull);
        if (readLoss) {
          expect(
            find.byKey(const ValueKey('business-field-description')),
            findsNothing,
          );
        }
        await tapText(tester, 'Schließen');
        expect(find.byType(AlertDialog), findsNothing);
        expect(tester.takeException(), isNull);
      },
    );

    financialWidgets(
      'Cancellation dialog respects fresh ${readLoss ? 'read' : 'issue'} loss and returns',
      (tester) async {
        final api = FinancialNavigationApi()..finalDocument = true;
        final session = await showFeature(tester, api, 'Belege');
        await openDocument(tester);
        await tapText(tester, 'Stornoentwurf erstellen');
        await tester.enterText(
          find.byKey(const ValueKey('business-field-reason')),
          'Vertrauliche Korrektur',
        );
        api.permissions.remove(readLoss ? 'finance.read' : 'finance.issue');
        await session.load();
        await tester.pumpAndSettle();
        expect(tester.widget<FilledButton>(saveButton()).onPressed, isNull);
        if (readLoss) expect(find.text('Vertrauliche Korrektur'), findsNothing);
        expect(api.calls.where((c) => c.body != null), isEmpty);
        await tapText(tester, 'Schließen');
        expect(tester.takeException(), isNull);
      },
    );
  }

  financialWidgets(
    'Payment validation, server error, close and reopen preserve navigation',
    (tester) async {
      final api = FinancialNavigationApi()..failPayment = true;
      await showFeature(tester, api, 'Finanzen');
      await tapText(tester, 'Zahlung erfassen');
      await tapText(tester, 'Speichern');
      expect(find.textContaining('Bitte buchungshinweis'), findsWidgets);
      await tester.enterText(
        find.byKey(const ValueKey('business-field-reference')),
        'Beleg NAV',
      );
      await tapText(tester, 'Speichern');
      expect(find.text('Buchungshinweis bitte prüfen'), findsOneWidget);
      await tapText(tester, 'Schließen');
      await tapText(tester, 'Zahlung erfassen');
      expect(find.text('Buchungshinweis bitte prüfen'), findsNothing);
      api.failPayment = false;
      await tester.enterText(
        find.byKey(const ValueKey('business-field-reference')),
        'Korrigierter Beleg NAV',
      );
      await tapText(tester, 'Speichern');
      expect(find.byType(AlertDialog), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Manual position cancel preserves data and save returns the edited row',
    (tester) async {
      final api = FinancialNavigationApi();
      await showFeature(tester, api, 'Belege');
      await openManualPosition(tester);
      await tester.enterText(
        find.byKey(const ValueKey('business-field-description')),
        'Verworfene Änderung',
      );
      await tapText(tester, 'Schließen');
      expect(find.text('Verworfene Änderung'), findsNothing);
      await tapText(tester, 'Vertrauliche Montage');
      await tester.enterText(
        find.byKey(const ValueKey('business-field-description')),
        'Bestätigte Änderung',
      );
      await tapText(tester, 'Speichern');
      expect(find.byType(AlertDialog), findsNothing);
      expect(find.text('Bestätigte Änderung'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Rechnung zur Navigation'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Cancellation creates the canonical credit note and its editor returns cleanly',
    (tester) async {
      final api = FinancialNavigationApi()..finalDocument = true;
      await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'Stornoentwurf erstellen');
      await tester.enterText(
        find.byKey(const ValueKey('business-field-reason')),
        'Korrektur zur Navigation',
      );
      await tapText(tester, 'Speichern');
      expect(find.text('Storno zur Navigation'), findsOneWidget);
      expect(find.textContaining('Stornogutschrift'), findsWidgets);
      await tapText(tester, 'Entwurf bearbeiten');
      expect(find.textContaining('Stornogutschrift'), findsWidgets);
      expect(tester.takeException(), isNull);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Storno zur Navigation'), findsOneWidget);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Rechnung zur Navigation'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Classification dialog loses its source fields on fresh classify revocation',
    (tester) async {
      final api = FinancialNavigationApi();
      final session = await showFeature(tester, api, 'Unterlagenfreigabe');
      await tapText(tester, 'Freigabe prüfen');
      api.permissions.remove('documents.classify');
      await session.load();
      await tester.pumpAndSettle();
      expect(find.byType(DropdownButtonFormField<String>), findsNothing);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Freigabe speichern'),
            )
            .onPressed,
        isNull,
      );
      await tapText(tester, 'Schließen');
      expect(find.text('Freigaben nicht verfügbar'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Dunning confirmation cannot submit after approval permission is removed',
    (tester) async {
      final api = FinancialNavigationApi();
      final session = await showFeature(tester, api, 'Finanzen');
      await tapText(tester, 'Mahnlauf vorbereiten');
      await tapText(tester, 'Fassung prüfen und freigeben');
      api.permissions.remove('finance.approve');
      await session.load();
      await tester.pumpAndSettle();
      await tapText(tester, 'Geprüfte Fassung freigeben');
      expect(api.calls.where((c) => c.path.endsWith('/approve')), isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Finalize confirmation cannot submit after issue permission is removed',
    (tester) async {
      final api = FinancialNavigationApi();
      final session = await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'Festschreiben');
      api.permissions.remove('finance.issue');
      await session.load();
      await tester.pumpAndSettle();
      await tapText(tester, 'Festschreiben');
      expect(api.calls.where((c) => c.path.endsWith('/finalize')), isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Mail confirmation cannot submit after approval permission is removed',
    (tester) async {
      final api = FinancialNavigationApi()..finalDocument = true;
      final session = await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'E-Mail prüfen', settle: false);
      api.permissions.remove('finance.approve');
      await session.load();
      await tester.pump(const Duration(milliseconds: 400));
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Geprüfte E-Mail freigeben'),
            )
            .onPressed,
        isNull,
      );
      await tapText(tester, 'Abbrechen');
      expect(api.calls.where((c) => c.path.endsWith('/email')), isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Mail preview disappears when financial read is revoked during confirmation',
    (tester) async {
      final api = FinancialNavigationApi()..finalDocument = true;
      final session = await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'E-Mail prüfen', settle: false);
      expect(
        find.textContaining('Vertraulicher Rechnungstext'),
        findsOneWidget,
      );
      api.permissions.remove('finance.read');
      await session.load();
      await tester.pump(const Duration(milliseconds: 400));
      expect(find.textContaining('Vertraulicher Rechnungstext'), findsNothing);
      expect(
        tester
            .widget<FilledButton>(
              find.widgetWithText(FilledButton, 'Geprüfte E-Mail freigeben'),
            )
            .onPressed,
        isNull,
      );
      await tapText(tester, 'Abbrechen');
      expect(api.calls.where((c) => c.path.endsWith('/email')), isEmpty);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Mail preview cancellation and explicit confirmation return to the document',
    (tester) async {
      final api = FinancialNavigationApi()..finalDocument = true;
      await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'E-Mail prüfen', settle: false);
      await tapText(tester, 'Abbrechen');
      expect(api.calls.where((c) => c.path.endsWith('/email')), isEmpty);
      await tapText(tester, 'E-Mail prüfen', settle: false);
      await tapText(tester, 'Geprüfte E-Mail freigeben');
      expect(api.calls.where((c) => c.path.endsWith('/email')), hasLength(1));
      expect(
        find.text(
          'Versandfreigabe gespeichert. Der Versand ist noch nicht bestätigt.',
        ),
        findsOneWidget,
      );
      expect(find.byType(AlertDialog), findsNothing);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Rechnung zur Navigation'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Finance successful refresh replaces a previous failure with its empty state',
    (tester) async {
      final api = FinancialNavigationApi()..failFinance = true;
      await showFeature(tester, api, 'Finanzen');
      expect(find.textContaining('Finanzen vorübergehend'), findsOneWidget);
      api
        ..failFinance = false
        ..emptyFinance = true;
      final refresh = tester.state<RefreshIndicatorState>(
        find.byType(RefreshIndicator),
      );
      final pending = refresh.show();
      await tester.pumpAndSettle();
      await pending;
      expect(find.textContaining('Finanzen vorübergehend'), findsNothing);
      expect(find.text('Keine offenen Posten'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Access successful reload replaces a previous failure with its empty state',
    (tester) async {
      final api = FinancialNavigationApi()..failAccess = true;
      await showFeature(tester, api, 'Unterlagenfreigabe');
      expect(find.textContaining('Freigaben vorübergehend'), findsOneWidget);
      api
        ..failAccess = false
        ..emptyAccess = true;
      await tester.tap(find.byTooltip('Freigaben neu laden'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Freigaben vorübergehend'), findsNothing);
      expect(find.text('Keine prüfbaren Unterlagen'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  financialWidgets(
    'Document retry through edit and back clears its previous load error',
    (tester) async {
      final api = FinancialNavigationApi();
      await showFeature(tester, api, 'Belege');
      await openDocument(tester);
      await tapText(tester, 'Entwurf bearbeiten');
      api.failDocument = true;
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.textContaining('Archiv vorübergehend'), findsOneWidget);
      api.failDocument = false;
      await tapText(tester, 'Entwurf bearbeiten');
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.textContaining('Archiv vorübergehend'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );
}

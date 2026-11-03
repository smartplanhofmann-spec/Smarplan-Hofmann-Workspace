import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_accounting.dart';
import 'package:smartplan_office/business_accounting_profile.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/design.dart';

import 'business_accounting_test.dart' as base;

const path = '/api/business/accounting/profile';
const key = 'accounting-profile';
const flags = {
  'scope': 'organization_profile',
  'tax_status': 'unconfigured',
  'tax_result_available': false,
};
Map<String, dynamic> get unknownProfile => {
  'legal_form': 'sole_proprietorship',
  'accounting_method': 'euer',
  'vat_regime': null,
  'vat_timing': null,
  'vat_effective_from': null,
  'bookkeeping_start': null,
};

class ProfileApi extends base.AccountingApi {
  bool profileFeature = true,
      profileModule = true,
      profileDenied = false,
      loseConfirm = false,
      beforeServer = false,
      paginated = false;
  int revision = 0, generation = 1;
  int? confirmStatus;
  String? resolution;
  Completer<void>? previewReply, confirmReply, historyReply, stateReply;
  final versions = <Map<String, dynamic>>[];
  final requests = <String, Map<String, dynamic>>{},
      results = <String, Map<String, dynamic>>{};
  Map<String, dynamic> get profileState => {
    'revision': revision,
    'state_hash': revision.toRadixString(16).padLeft(64, '0'),
    'preparation_status': revision == 0 ? 'unrecorded' : 'recorded',
    'current': versions.isEmpty ? null : versions.last,
    'writes_allowed':
        writes && !readonly && enabled && rights.contains('accounting.admin'),
    ...flags,
  };
  Map<String, dynamic> proposal(Map<String, dynamic> body) => {
    ...base.copy(body),
    'preview_hash': 'b' * 64,
    ...flags,
  };
  Map<String, dynamic> addVersion({
    Map<String, dynamic>? profile,
    String reason = 'Gespeicherter Grund',
    String evidence = 'Gespeicherter Nachweis',
  }) {
    final prior = profileState['state_hash'];
    revision++;
    final entry = {
      'id': revision.toRadixString(16).padLeft(32, '0'),
      'revision': revision,
      'previous_state_hash': prior,
      'profile': profile ?? unknownProfile,
      'reason': reason,
      'evidence_reference': evidence,
      'preview_hash': 'b' * 64,
      'created_by': 'a' * 32,
      'created_at': '2026-11-03T12:00:00Z',
      ...flags,
    };
    versions.add(base.copy(entry));
    return base.copy(entry);
  }

  @override
  Future<dynamic> call(String routePath, [Map<String, dynamic>? body]) async {
    final route = routePath.split('?').first;
    if (route == '/api/business/capabilities') {
      final value = base.copy(
        await super.call(routePath, body) as Map<String, dynamic>,
      );
      value['generation'] = generation;
      if (profileFeature)
        (value['features'] as List).add('accounting_preparation_profile');
      if (profileModule)
        (value['capabilities'] as List).add('business_accounting_profile');
      return value;
    }
    if (!route.startsWith(path)) return super.call(routePath, body);
    calls.add((path: routePath, body: body == null ? null : base.copy(body)));
    if (profileDenied)
      throw const ApiException(403, 'Profil nicht mehr freigegeben');
    if (body == null) {
      if (route.endsWith('/history')) {
        final values = versions.reversed.toList();
        final offset = int.parse(
          Uri.parse(routePath).queryParameters['offset'] ?? '0',
        );
        final items = paginated ? values.skip(offset).take(1).toList() : values;
        final result = {
          'items': items,
          'total': values.length,
          'next_offset': paginated && offset + 1 < values.length
              ? offset + 1
              : null,
          'scope': 'organization_profile',
        };
        if (historyReply != null) await historyReply!.future;
        return base.copy(result);
      }
      final value = base.copy(profileState);
      if (stateReply != null) await stateReply!.future;
      return value;
    }
    if (route.endsWith('/preview')) {
      if (previewReply != null) await previewReply!.future;
      return proposal(body);
    }
    if (route.endsWith('/confirm')) {
      if (confirmStatus != null)
        throw ApiException(
          confirmStatus!,
          'Unklare Profilantwort',
          requestResolution: resolution,
        );
      if (beforeServer) {
        beforeServer = false;
        throw const ApiException(0, 'Unklare Übertragung');
      }
      final id = body['request_id'] as String;
      if (requests.containsKey(id)) {
        if (jsonEncode(requests[id]) != jsonEncode(body))
          throw const ApiException(409, 'Anderer Auftrag');
        return base.copy(results[id]!);
      }
      if (body['expected_revision'] != revision ||
          body['state_hash'] != profileState['state_hash']) {
        throw const ApiException(
          409,
          'Profilstand wurde geändert',
          requestResolution: 'not_accepted',
        );
      }
      final result = addVersion(
        profile: base.copy(body['profile']),
        reason: body['reason'],
        evidence: body['evidence_reference'],
      );
      requests[id] = base.copy(body);
      results[id] = base.copy(result);
      if (confirmReply != null) await confirmReply!.future;
      if (loseConfirm) {
        loseConfirm = false;
        throw const ApiException(0, 'Antwort nach Speicherung verloren');
      }
      return result;
    }
    throw StateError('Unexpected profile route $routePath');
  }
}

Future<BusinessSession> show(
  WidgetTester tester,
  ProfileApi api, {
  double width = 1200,
  bool accounting = false,
  bool offline = false,
  String? projectId,
}) async {
  await tester.binding.setSurfaceSize(Size(width, 1000));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  final session = BusinessSession(
    api: api,
    offlineMode: offline,
    projectId: projectId,
  );
  base.activeApi = api;
  base.activeSession = session;
  await session.load();
  await tester.pumpWidget(
    MaterialApp(
      theme: officeTheme(),
      home: accounting
          ? BusinessAccountingPage(session: session)
          : BusinessPreparationProfilePage(session: session),
    ),
  );
  await tester.pumpAndSettle();
  return session;
}

Future<void> fill(WidgetTester tester, String name, String value) async {
  final finder = find.byKey(ValueKey('profile-$name'));
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.enterText(finder, value);
  await tester.pump();
}

Future<void> choose(WidgetTester tester, String name, String label) async {
  final finder = find.byWidgetPredicate(
    (w) =>
        w is DropdownButtonFormField<String> &&
        '${w.key}'.contains('profile-$name-'),
  );
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
  await tester.tap(find.text(label).last);
  await tester.pumpAndSettle();
}

Future<void> toggle(WidgetTester tester, String name) async {
  final finder = find.byKey(ValueKey('profile-$name'));
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> preview(
  WidgetTester tester, {
  bool open = true,
  String reason = 'Ausdrücklich bestätigte Grundlagen',
  String evidence = 'Inhaberangabe SYN-1',
}) async {
  if (open) await base.press(tester, 'Neuen Vorbereitungsstand erfassen');
  await fill(tester, 'reason', reason);
  await fill(tester, 'evidence', evidence);
  await base.press(tester, 'Vorbereitungsstand vorschauen');
}

Future<void> confirm(WidgetTester tester) async {
  await toggle(tester, 'confirmation');
  await base.press(tester, 'Vorbereitungsstand verbindlich speichern');
}

void main() {
  for (final width in [390.0, 1200.0]) {
    base.accountingWidgetTest(
      'explicit incomplete profile preserves four nulls and requires confirmation at $width',
      (tester) async {
        final api = ProfileApi();
        await show(tester, api, width: width);
        expect(api.versions, isEmpty);
        expect(api.calls.where((c) => c.body != null), isEmpty);
        await base.press(tester, 'Neuen Vorbereitungsstand erfassen');
        expect(api.calls.where((c) => c.body != null), isEmpty);
        expect(find.textContaining('Vorgeschlagene Grundlage'), findsOneWidget);
        await preview(
          tester,
          open: false,
          reason: '  Inhaber erklärt EÜR  ',
          evidence: '  Eigene Angabe SYN-1  ',
        );
        final proposal = api.calls
            .lastWhere((c) => c.path.endsWith('/preview'))
            .body!;
        expect(proposal['profile'], unknownProfile);
        expect(proposal['reason'], '  Inhaber erklärt EÜR  ');
        expect(proposal['evidence_reference'], '  Eigene Angabe SYN-1  ');
        expect(api.versions, isEmpty);
        final button = find.widgetWithText(
          FilledButton,
          'Vorbereitungsstand verbindlich speichern',
        );
        expect(tester.widget<FilledButton>(button).onPressed, isNull);
        expect(find.text('Soll-/Istbesteuerung: Unbekannt'), findsOneWidget);
        await confirm(tester);
        expect(api.versions.single['profile'], unknownProfile);
        expect(api.versions.single['tax_result_available'], false);
        expect(
          find.text('Aktueller Vorbereitungsstand · Version 1'),
          findsOneWidget,
        );
        expect(
          find.text('Gespeicherter Vorbereitungsstand · Version 1'),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
      },
    );
  }
  for (final gate in [
    'feature',
    'module',
    'offline',
    'project',
    'finance.read',
    'accounting.read',
  ]) {
    base.accountingWidgetTest('$gate prevents profile endpoint probes', (
      tester,
    ) async {
      final api = ProfileApi();
      if (gate == 'feature') api.profileFeature = false;
      if (gate == 'module') api.profileModule = false;
      api.rights.remove(gate);
      await show(
        tester,
        api,
        offline: gate == 'offline',
        projectId: gate == 'project' ? 'f' * 32 : null,
      );
      expect(api.calls.where((c) => c.path.startsWith(path)), isEmpty);
      expect(
        find.text('Vorbereitungsprofil nicht freigegeben'),
        findsOneWidget,
      );
    });
  }
  for (final gate in ['admin', 'readonly', 'disabled', 'writes']) {
    base.accountingWidgetTest(
      '$gate keeps profile history readable without editing',
      (tester) async {
        final api = ProfileApi()..addVersion();
        if (gate == 'admin') api.rights.remove('accounting.admin');
        if (gate == 'readonly') api.readonly = true;
        if (gate == 'disabled') api.enabled = false;
        if (gate == 'writes') api.writes = false;
        await show(tester, api);
        expect(
          find.text('Aktueller Vorbereitungsstand · Version 1'),
          findsOneWidget,
        );
        expect(find.text('Neuen Vorbereitungsstand erfassen'), findsNothing);
        expect(api.calls.where((c) => c.body != null), isEmpty);
      },
    );
  }
  base.accountingWidgetTest(
    'admin can record a profile without cash preparation or finance write',
    (tester) async {
      final api = ProfileApi()
        ..rights = {'accounting.read', 'finance.read', 'accounting.admin'};
      await show(tester, api);
      await preview(tester);
      await confirm(tester);
      expect(api.versions, hasLength(1));
    },
  );
  base.accountingWidgetTest(
    'cash preparation rights cannot replace profile admin',
    (tester) async {
      final api = ProfileApi()
        ..rights = {
          'accounting.read',
          'finance.read',
          'accounting.prepare',
          'finance.write',
        };
      await show(tester, api);
      expect(find.text('Neuen Vorbereitungsstand erfassen'), findsNothing);
    },
  );
  for (final supported in [true, false]) {
    base.accountingWidgetTest(
      'accounting entry preserves old status with profile support $supported',
      (tester) async {
        final api = ProfileApi()..profileFeature = supported;
        await show(tester, api, accounting: true);
        if (supported) {
          await base.press(tester, 'Vorbereitungsprofil ansehen');
          expect(
            find.text('Noch kein Vorbereitungsstand gespeichert'),
            findsOneWidget,
          );
        } else {
          expect(find.text('Vorbereitungsprofil ansehen'), findsNothing);
          expect(
            find.textContaining('Steuerprofil nicht eingerichtet'),
            findsOneWidget,
          );
        }
        expect(api.calls.where((c) => c.body != null), isEmpty);
      },
    );
  }
  base.accountingWidgetTest(
    'explicit VAT facts and independent dates remain documentary',
    (tester) async {
      final api = ProfileApi();
      await show(tester, api);
      await base.press(tester, 'Neuen Vorbereitungsstand erfassen');
      await choose(tester, 'vat-regime', 'Regelbesteuerung');
      await choose(tester, 'vat-timing', 'Sollbesteuerung');
      await toggle(tester, 'vat-date-known');
      await fill(tester, 'vat-date', '1.1.2025');
      await toggle(tester, 'bookkeeping-date-known');
      await fill(tester, 'bookkeeping-date', '03.11.2026');
      await preview(tester, open: false);
      await confirm(tester);
      expect(api.versions.single['profile'], {
        ...unknownProfile,
        'vat_regime': 'regular',
        'vat_timing': 'accrual',
        'vat_effective_from': '2025-01-01',
        'bookkeeping_start': '2026-11-03',
      });
      expect(api.versions.single['tax_status'], 'unconfigured');
      expect(
        find.textContaining('Diese Angaben aktivieren keine Steuerregel'),
        findsNWidgets(2),
      );
    },
  );
  base.accountingWidgetTest(
    'unknown controls clear prior declared VAT timing and dates explicitly',
    (tester) async {
      final api = ProfileApi()
        ..addVersion(
          profile: {
            ...unknownProfile,
            'vat_regime': 'regular',
            'vat_timing': 'cash',
            'vat_effective_from': '2025-01-01',
            'bookkeeping_start': '2026-01-01',
          },
        );
      await show(tester, api);
      await base.press(tester, 'Neuen Vorbereitungsstand erfassen');
      await choose(tester, 'vat-regime', 'Unbekannt');
      await toggle(tester, 'bookkeeping-date-known');
      await preview(tester, open: false);
      await confirm(tester);
      expect(api.versions.last['profile'], unknownProfile);
      expect(api.versions.first['profile']['vat_timing'], 'cash');
    },
  );
  base.accountingWidgetTest(
    'small business clears timing but permits an unknown effective date',
    (tester) async {
      final api = ProfileApi();
      await show(tester, api);
      await base.press(tester, 'Neuen Vorbereitungsstand erfassen');
      await choose(tester, 'vat-regime', 'Regelbesteuerung');
      await choose(tester, 'vat-timing', 'Istbesteuerung');
      await choose(tester, 'vat-regime', 'Kleinunternehmerregelung');
      await preview(tester, open: false);
      expect(
        api.calls
            .lastWhere((c) => c.path.endsWith('/preview'))
            .body!['profile'],
        {...unknownProfile, 'vat_regime': 'small_business'},
      );
    },
  );
  for (final invalid in ['', '31.02.2026', '1899-12-31', '2201-01-01']) {
    base.accountingWidgetTest('known invalid date $invalid cannot preview', (
      tester,
    ) async {
      final api = ProfileApi();
      await show(tester, api);
      await base.press(tester, 'Neuen Vorbereitungsstand erfassen');
      await toggle(tester, 'bookkeeping-date-known');
      await fill(tester, 'bookkeeping-date', invalid);
      await preview(tester, open: false);
      expect(api.calls.where((c) => c.path.endsWith('/preview')), isEmpty);
      expect(
        find.textContaining('gültigen Kalendertag zwischen 1900 und 2200'),
        findsOneWidget,
      );
    });
  }
  for (final invalid in ['', '   ', 'Ungültig\u007f', 'x' * 1001]) {
    base.accountingWidgetTest(
      'invalid reason ${invalid.length} blocks preview',
      (tester) async {
        final api = ProfileApi();
        await show(tester, api);
        await preview(tester, reason: invalid);
        expect(api.calls.where((c) => c.path.endsWith('/preview')), isEmpty);
      },
    );
  }
  base.accountingWidgetTest(
    'new version history appends without overwriting prior entry and pages separately',
    (tester) async {
      final api = ProfileApi()..paginated = true;
      final old = api.addVersion();
      api.addVersion(reason: 'Zweite bestätigte Angabe');
      await show(tester, api);
      expect(
        find.text('Gespeicherter Vorbereitungsstand · Version 1'),
        findsNothing,
      );
      await tester.scrollUntilVisible(
        find.text('Weitere Profilversionen laden'),
        400,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await base.press(tester, 'Weitere Profilversionen laden');
      expect(
        find.text('Gespeicherter Vorbereitungsstand · Version 1'),
        findsOneWidget,
      );
      await tester.scrollUntilVisible(
        find.text('Neuen Vorbereitungsstand erfassen'),
        -400,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await preview(tester);
      await confirm(tester);
      expect(api.versions.first, old);
      expect(api.versions, hasLength(3));
    },
  );
  base.accountingWidgetTest(
    'concurrent revision after preview requires a fresh proposal without new partial version',
    (tester) async {
      final api = ProfileApi();
      final session = await show(tester, api);
      await preview(tester);
      api.addVersion(reason: 'Andere ausdrücklich bestätigte Version');
      await confirm(tester);
      expect(api.versions, hasLength(1));
      expect(session.pending(key), false);
      expect(find.text('Profilstand wurde geändert'), findsOneWidget);
      expect(find.text('Neuen Vorbereitungsstand erfassen'), findsOneWidget);
    },
  );
  base.accountingWidgetTest(
    'lost acknowledgement reopens neutrally and repeats original after later version',
    (tester) async {
      final api = ProfileApi()..loseConfirm = true;
      final session = await show(tester, api);
      await preview(tester);
      await confirm(tester);
      final original = api.calls.lastWhere((c) => c.path.endsWith('/confirm'));
      expect(session.pending(key), true);
      api.addVersion(reason: 'Spätere Profilversion');
      api.generation = 2;
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: BusinessPreparationProfilePage(session: session),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Vorbereitungsstand prüfen'), findsNothing);
      expect(find.byType(TextField), findsNothing);
      expect(find.text('Neuen Vorbereitungsstand erfassen'), findsNothing);
      await base.press(tester, 'Unverändert erneut senden');
      final replay = api.calls.lastWhere((c) => c.path.endsWith('/confirm'));
      expect(replay.path, original.path);
      expect(replay.body, original.body);
      expect(api.versions, hasLength(2));
      expect(session.pending(key), false);
    },
  );
  for (final status in [403, 404, 409]) {
    base.accountingWidgetTest(
      'first unresolved confirm $status retains exact pending and hides editor',
      (tester) async {
        final api = ProfileApi()..confirmStatus = status;
        final session = await show(tester, api);
        await preview(tester);
        await confirm(tester);
        expect(session.pending(key), true);
        expect(find.byType(TextField), findsNothing);
        api.confirmStatus = null;
        await tester.pumpWidget(const SizedBox());
        await tester.pumpWidget(
          MaterialApp(
            theme: officeTheme(),
            home: BusinessPreparationProfilePage(session: session),
          ),
        );
        await tester.pumpAndSettle();
        await base.press(tester, 'Unverändert erneut senden');
        final sent = api.calls
            .where((c) => c.path.endsWith('/confirm'))
            .toList();
        expect(sent.last.body, sent.first.body);
        expect(api.versions, hasLength(1));
      },
    );
  }
  base.accountingWidgetTest(
    'fresh admin loss before confirmation hides loaded profile and prevents POST',
    (tester) async {
      final api = ProfileApi();
      await show(tester, api);
      await preview(tester);
      api.rights.remove('accounting.admin');
      await confirm(tester);
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), isEmpty);
      expect(find.text('Vorbereitungsstand prüfen'), findsNothing);
      expect(find.byType(TextField), findsNothing);
    },
  );
  for (final invalid in ['', 'x' * 201]) {
    base.accountingWidgetTest(
      'invalid evidence reference ${invalid.length} blocks preview',
      (tester) async {
        final api = ProfileApi();
        await show(tester, api);
        await preview(tester, evidence: invalid);
        expect(api.calls.where((c) => c.path.endsWith('/preview')), isEmpty);
      },
    );
  }
  base.accountingWidgetTest(
    'read revocation clears current history and unsaved private editor',
    (tester) async {
      final api = ProfileApi()..addVersion(reason: 'PRIVATE-HISTORY');
      final session = await show(tester, api);
      await base.press(tester, 'Neuen Vorbereitungsstand erfassen');
      await fill(tester, 'evidence', 'PRIVATE-UNSAVED');
      api.rights.remove('finance.read');
      await session.load();
      await tester.pumpAndSettle();
      expect(find.textContaining('PRIVATE-HISTORY'), findsNothing);
      expect(find.text('PRIVATE-UNSAVED'), findsNothing);
      expect(find.byType(TextField), findsNothing);
    },
  );
  base.accountingWidgetTest(
    'original ACK during reopened history read discards stale pending view',
    (tester) async {
      final api = ProfileApi();
      final session = await show(tester, api);
      await preview(tester);
      await toggle(tester, 'confirmation');
      api.confirmReply = Completer<void>();
      final confirmButton = find.text(
        'Vorbereitungsstand verbindlich speichern',
      );
      await tester.ensureVisible(confirmButton);
      await tester.pumpAndSettle();
      await tester.tap(confirmButton);
      await tester.pump();
      expect(session.pending(key), true);
      await tester.pumpWidget(const SizedBox());
      api.historyReply = Completer<void>();
      await tester.pumpWidget(
        MaterialApp(
          theme: officeTheme(),
          home: BusinessPreparationProfilePage(session: session),
        ),
      );
      await tester.pump();
      api.confirmReply!.complete();
      await tester.pump();
      api.historyReply!.complete();
      await tester.pumpAndSettle();
      expect(session.pending(key), false);
      expect(find.text('Unverändert erneut senden'), findsNothing);
      expect(
        find.text('Aktueller Vorbereitungsstand · Version 1'),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.path.endsWith('/confirm')), hasLength(1));
    },
  );
  base.accountingWidgetTest(
    'logout during preview drops late profile details',
    (tester) async {
      final api = ProfileApi();
      final session = await show(tester, api);
      await base.press(tester, 'Neuen Vorbereitungsstand erfassen');
      await fill(tester, 'reason', 'Geheim');
      await fill(tester, 'evidence', 'Privater Nachweis');
      api.previewReply = Completer<void>();
      final button = find.text('Vorbereitungsstand vorschauen');
      await tester.ensureVisible(button);
      await tester.pumpAndSettle();
      await tester.tap(button);
      await tester.pump();
      api.token = null;
      api.previewReply!.complete();
      await tester.pumpAndSettle();
      expect(session.pending(key), false);
      expect(find.textContaining('Privater Nachweis'), findsNothing);
      expect(
        find.text('Vorbereitungsprofil nicht freigegeben'),
        findsOneWidget,
      );
    },
  );
}

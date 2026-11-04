import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/business_assistant.dart';
import 'package:smartplan_office/business_session.dart';
import 'package:smartplan_office/business_speech.dart';

Map<String, dynamic> copy(dynamic value) => jsonDecode(jsonEncode(value));
List<Map<String, dynamic>> companies() =>
    (jsonDecode(
              File(
                '../docs/evidence/company-assistant-isolation-independent-2026-11-04/actual-two-company-responses.json',
              ).readAsStringSync(),
            )['companies']
            as List)
        .map(copy)
        .toList();

class ActualCompanyApi extends OfficeApi {
  ActualCompanyApi(this.company)
    : super(
        baseUrl:
            'https://${company['marker'].toString().replaceFirst('ONLY', '').toLowerCase()}.example.test',
        apiVersion: 'v1',
      ) {
    token = 'synthetic-native-${company['instance_id']}';
  }
  final Map<String, dynamic> company;
  Completer<dynamic>? heldSources;
  final paths = <String>[];
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    paths.add(path);
    if (body != null) throw StateError('Read-only review unexpected mutation');
    if (path.startsWith('/api/business/capabilities'))
      return copy(company['capabilities']);
    if (path == '/api/me') return copy(company['me']);
    if (path.contains('/assistant/speech/status?'))
      return copy(company['speech_provider_status']);
    if (path.contains('/assistant/status?'))
      return copy(company['assistant_status']);
    if (path.contains('/assistant/sources?'))
      return heldSources?.future ?? copy(company['search']);
    if (path.contains('/assistant/rules?')) return copy(company['rules']);
    if (path.contains('/assistant/plans?')) return copy(company['plans']);
    if (path.contains('/assistant/chat?')) return copy(company['chats']);
    if (path.endsWith('/assistant/contexts/${company['context']['id']}'))
      return copy(company['context']);
    throw StateError('Unexpected read $path');
  }
}

BusinessSession companySession(ActualCompanyApi api) => BusinessSession(
  api: api,
  projectId: api.company['project'],
  projects: [
    {'id': api.company['project'], 'name': api.company['marker']},
  ],
);

void main() {
  final actual = companies(), a = actual[0], b = actual[1];
  test('independent actual company chat and speech readers accept only each selected original', () {
    for (final own in actual) {
      expect(
        assistantAnswerValues(own['context'], own['chat'])['facts']
            .map((fact) => fact['value']).toList(),
        ['${own['marker']} project', '${own['marker']} original'],
      );
      expect(
        speechDraftResult(
          own['speech'],
          requestId: own['speech']['id'],
          projectId: own['project'],
          contextId: own['context']['id'],
          contextSha256: own['context']['sha256'],
        ),
        own['speech']['text'],
      );
    }
    expect(
      () => assistantAnswerValues(b['context'], a['chat']),
      throwsA(isA<FormatException>()),
    );
    expect(
      () => speechDraftResult(
        a['speech'],
        requestId: b['speech']['id'],
        projectId: b['project'],
        contextId: b['context']['id'],
        contextSha256: b['context']['sha256'],
      ),
      throwsA(isA<ApiException>()),
    );
  });
  for (final pending in [false, true]) {
    testWidgets(
      'independent actual company host and parent session replacement discards ${pending ? 'held source response' : 'visible private chat'}',
      (t) async {
        t.view.physicalSize = const Size(1500, 2000);
        t.view.devicePixelRatio = 1;
        final apiA = ActualCompanyApi(a), apiB = ActualCompanyApi(b);
        if (pending) apiA.heldSources = Completer<dynamic>();
        final sessionA = companySession(apiA), sessionB = companySession(apiB);
        final selected = ValueNotifier(sessionA);
        try {
          await sessionA.load();
          await sessionB.load();
          await t.pumpWidget(
            MaterialApp(
              home: ValueListenableBuilder<BusinessSession>(
                valueListenable: selected,
                builder: (_, s, child) =>
                    Scaffold(body: BusinessAssistantPage(session: s)),
              ),
            ),
          );
          if (pending) {
            for (var i = 0; i < 10; i++) {
              await t.pump();
            }
            expect(
              apiA.paths.any((p) => p.contains('/assistant/sources?')),
              true,
            );
          } else {
            await t.pumpAndSettle();
            expect(find.text(a['chat']['message']), findsOneWidget);
          }
          expect(apiA.base, isNot(apiB.base));
          selected.value = sessionB;
          await t.pump();
          if (pending) apiA.heldSources!.complete(copy(a['search']));
          await t.pumpAndSettle();
          expect(find.text(a['chat']['message']), findsNothing);
          expect(find.text(b['chat']['message']), findsOneWidget);
          expect(
            apiB.paths.any((p) => p.contains('/assistant/sources?')),
            true,
          );
          expect(t.takeException(), null);
        } finally {
          await t.pumpWidget(const SizedBox.shrink());
          selected.dispose();
          sessionA.dispose();
          sessionB.dispose();
          apiA.dispose();
          apiB.dispose();
          t.view.resetPhysicalSize();
          t.view.resetDevicePixelRatio();
        }
      },
    );
  }
}

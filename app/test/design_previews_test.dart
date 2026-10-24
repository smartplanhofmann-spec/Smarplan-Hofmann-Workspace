import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/design.dart';
import 'package:smartplan_office/inquiry_pages.dart';
import 'package:smartplan_office/project_workspace_page.dart';

import 'inquiry_widget_test.dart' show InquiryApi, inquiryId;
import 'project_workspace_widget_test.dart' show WorkspaceApi;

// Real widgets and fonts with synthetic in-process replies. CI may retain PNGs
// for visual review; normal runs do not write any screenshots.
void main() {
  final boundary = GlobalKey();
  setUpAll(() async {
    await (FontLoader(
      'Inter',
    )..addFont(rootBundle.load('assets/fonts/Inter.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });

  Future<void> mount(WidgetTester tester, Widget page, bool phone) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = phone
        ? const Size(390, 840)
        : const Size(1280, 1000);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      RepaintBoundary(
        key: boundary,
        child: MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: officeTheme(),
          home: page,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  }

  Future<void> capture(WidgetTester tester, String name) async {
    if (Platform.environment['SMARTPLAN_CAPTURE_UI'] != '1') return;
    final output = Platform.environment['SMARTPLAN_UI_OUTPUT'];
    expect(
      output,
      isNotNull,
      reason: 'Explicit UI capture needs its output path',
    );
    await tester.runAsync(() async {
      final rendered = tester.renderObject<RenderRepaintBoundary>(
        find.byKey(boundary),
      );
      final image = await rendered.toImage(pixelRatio: 1);
      try {
        final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
        final directory = Directory(output!);
        await directory.create(recursive: true);
        await File(directory.path + '/smartplan-0101-' + name + '.png')
            .writeAsBytes(bytes!.buffer.asUint8List(), flush: true);
      } finally {
        image.dispose();
      }
    });
  }

  for (final phone in [false, true]) {
    final suffix = phone ? 'phone' : 'desktop';
    testWidgets('Project work remains reachable with real fonts on ' + suffix, (
      tester,
    ) async {
      final api = WorkspaceApi()..token = 'synthetic-session';
      api.items['tasks']!.addAll([
        {
          'id': 'e' * 32,
          'revision': 1,
          'title': 'Bestand vor Ort prüfen',
          'details': '',
          'status': 'todo',
          'priority': 'normal',
          'due_date': '2030-12-31',
          'assignee_id': 'b' * 32,
        },
        {
          'id': 'f' * 32,
          'revision': 1,
          'title': 'Grundriss mit dem Kunden abstimmen',
          'details': '',
          'status': 'in_progress',
          'priority': 'normal',
          'due_date': null,
          'assignee_id': 'a' * 32,
        },
      ]);
      api.items['appointments']!.add({
        'id': 'c' * 32,
        'revision': 1,
        'title': 'Besprechung zum Aufmaß',
        'details': '',
        'start_at': '2030-12-12T09:00:00+00:00',
        'end_at': '2030-12-12T10:00:00+00:00',
        'status': 'scheduled',
      });
      await mount(
        tester,
        ProjectWorkspacePage(
          api: api,
          project: WorkspaceApi.project,
          role: 'owner',
          reportsBuilder: (_) => const SizedBox(),
        ),
        phone,
      );
      expect(find.text('Aufgabe anlegen').hitTestable(), findsOneWidget);
      expect(find.text('Bestand vor Ort prüfen').hitTestable(), findsOneWidget);
      await capture(tester, 'project-' + suffix);
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    });

    testWidgets('Inbox keeps the actual first request visible on ' + suffix, (
      tester,
    ) async {
      final api = InquiryApi()..token = 'synthetic-session';
      api.records[inquiryId] = {
        ...api.fixture(source: 'gmail', status: 'callback'),
        'subject': 'Aufmaß für die Modernisierung',
        'sender_name': 'Fiktive Hausverwaltung',
        'next_action': 'Rückruf und Termin abstimmen',
      };
      api.records['second'] = {
        ...api.fixture(source: 'whatsapp', status: 'review'),
        'id': 'second',
        'subject': 'Unterlagen zum Erdgeschoss',
        'sender_name': 'Fiktive Eigentümerin',
        'next_action': 'Grundriss und Fotos prüfen',
      };
      await mount(tester, InquiriesPage(api: api, role: 'owner'), phone);
      expect(find.text('Anfrage erfassen').hitTestable(), findsOneWidget);
      expect(
        find.text('Aufmaß für die Modernisierung').hitTestable(),
        findsOneWidget,
      );
      await capture(tester, 'inbox-' + suffix);
      await tester.pumpWidget(const SizedBox());
      api.dispose();
    });
  }
}

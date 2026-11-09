import 'dart:convert';
import 'dart:io';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smartplan_office/api.dart';
import 'package:smartplan_office/main.dart';
import 'package:smartplan_office/offline_vault.dart';
import 'package:smartplan_office/project_creation_journal.dart';

import 'project_create_replay_test.dart' show CreateApi;
import 'project_creation_journal_test.dart'
    show JournalDevice, FailingDevice, account, instance;
import 'project_creation_journal_http_test.dart' show until;

class DurableCreateApi extends CreateApi {
  String currentRole = 'owner';
  int? receiptError;
  void Function()? onReceipt;
  @override
  Future<dynamic> call(String path, [Map<String, dynamic>? body]) async {
    if (path == '/api/me')
      return {
        'id': account,
        'email': 'owner@example.test',
        'role': currentRole,
      };
    if (path.split('?').first == '/api/business/capabilities') {
      final value = Map<String, dynamic>.from(await super.call(path, body));
      value['features'] = [
        ...(value['features'] as List),
        'project_creation_journal',
      ];
      value['project_creation_scope'] = {
        'schema_version': 1,
        'account_id': account,
        'instance_id': instance,
      };
      return value;
    }
    if (path.startsWith('/api/business/project-creations/')) {
      if (receiptError != null)
        throw ApiException(receiptError!, 'Synthetic receipt read denied');
      final original = posts.last;
      final normalized = {
        'customer': original['customer'],
        'customer_id': original['customer_id'],
        'name': original['name'],
        'request_id': original['request_id'],
      };
      final hash = (await Sha256().hash(
        utf8.encode(
          jsonEncode({
            'data': normalized,
            'operation': 'core.project.create:v1',
          }),
        ),
      )).bytes.map((n) => n.toRadixString(16).padLeft(2, '0')).join();
      onReceipt?.call();
      return {
        'schema_version': 1,
        'instance_id': instance,
        'account_id': account,
        'request_id': original['request_id'],
        'request_hash': hash,
        'project_id': CreateApi.project,
      };
    }
    return super.call(path, body);
  }
}

class ToggleVault extends OfflineVault {
  final bool Function() fail;
  ToggleVault(super.directory, super.key, this.fail);
  @override
  Future<void> write(Map<String, dynamic> data) async {
    if (fail()) throw const FileSystemException('Synthetic clear failure');
    await super.write(data);
  }
}

class ToggleDevice extends JournalDevice {
  bool failWrites = false;
  ToggleDevice(super.folder);
  @override
  Future<OfflineVault> open(
    String server,
    String user, {
    bool create = false,
  }) async {
    final value = await super.open(server, user, create: create);
    return ToggleVault(value.directory, value.key, () => failWrites);
  }
}

Future<void> loginJournal(
  WidgetTester tester,
  DurableCreateApi api,
  ProjectCreationJournal journal,
) async {
  await tester.binding.setSurfaceSize(const Size(1200, 900));
  await tester.pumpWidget(OfficeApp(api: api, projectCreationJournal: journal));
  await tester.enterText(
    find.byType(TextFormField).at(0),
    'owner@example.test',
  );
  await tester.enterText(
    find.byType(TextFormField).at(1),
    'Synthetic-password-123',
  );
  await tester.tap(find.text('Anmelden'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Weitere Verwaltung'));
  await tester.pumpAndSettle();
}

Future<void> enterDurable(WidgetTester tester) async {
  await tester.tap(find.widgetWithText(FilledButton, 'Projekt anlegen'));
  await until(tester, () => find.byType(ProjectDialog).evaluate().isNotEmpty);
  await tester.pumpAndSettle();
  await tester.enterText(
    find.byType(TextFormField).first,
    'Synthetische Montage',
  );
  await tester.tap(find.byType(DropdownButtonFormField<String>));
  await tester.pumpAndSettle();
  await tester.tap(find.textContaining('Bestehender Kunde').last);
  await tester.pumpAndSettle();
}

void main() {
  for (final status in [403, 404]) {
    testWidgets(
      'accepted POST followed by receipt $status retains original across app recreation',
      (tester) async {
        final folder = (await tester.runAsync(
          () => Directory.systemTemp.createTemp('journal-receipt-'),
        ))!;
        final device = JournalDevice(folder),
            api = DurableCreateApi()..receiptError = status;
        try {
          await loginJournal(
            tester,
            api,
            ProjectCreationJournal(device: device),
          );
          await enterDurable(tester);
          await tester.tap(find.widgetWithText(FilledButton, 'Anlegen'));
          await until(
            tester,
            () => find
                .text('Synthetic receipt read denied')
                .evaluate()
                .isNotEmpty,
          );
          expect(api.posts, hasLength(1));
          final original = api.posts.single;
          expect(
            tester
                .widget<TextFormField>(find.byType(TextFormField).first)
                .enabled,
            isFalse,
          );
          await tester.pumpWidget(const SizedBox());
          await tester.pump();
          api.receiptError = null;
          await loginJournal(
            tester,
            api,
            ProjectCreationJournal(device: device),
          );
          await tester.tap(
            find.widgetWithText(FilledButton, 'Projekt anlegen'),
          );
          await until(
            tester,
            () => find.byType(ProjectDialog).evaluate().isNotEmpty,
          );
          await tester.tap(
            find.widgetWithText(FilledButton, 'Erneut versuchen'),
          );
          await until(
            tester,
            () => find.byType(ProjectDialog).evaluate().isEmpty,
          );
          expect(api.posts, [original, original]);
        } finally {
          await tester.pumpWidget(const SizedBox());
          api.dispose();
          await tester.runAsync(() => folder.delete(recursive: true));
          await tester.binding.setSurfaceSize(null);
        }
      },
    );
  }

  testWidgets(
    'accepted receipt with local clear failure remains exactly replayable',
    (tester) async {
      final folder = (await tester.runAsync(
        () => Directory.systemTemp.createTemp('journal-clear-'),
      ))!;
      final device = ToggleDevice(folder), api = DurableCreateApi();
      api.onReceipt = () => device.failWrites = true;
      try {
        await loginJournal(tester, api, ProjectCreationJournal(device: device));
        await enterDurable(tester);
        await tester.tap(find.widgetWithText(FilledButton, 'Anlegen'));
        await until(
          tester,
          () => find
              .textContaining('nicht lokal abgeschlossen')
              .evaluate()
              .isNotEmpty,
        );
        final original = api.posts.single;
        await tester.pumpWidget(const SizedBox());
        await tester.pump();
        device.failWrites = false;
        api.onReceipt = null;
        await loginJournal(tester, api, ProjectCreationJournal(device: device));
        await tester.tap(find.widgetWithText(FilledButton, 'Projekt anlegen'));
        await until(
          tester,
          () => find.byType(ProjectDialog).evaluate().isNotEmpty,
        );
        await tester.tap(find.widgetWithText(FilledButton, 'Erneut versuchen'));
        await until(
          tester,
          () => find.byType(ProjectDialog).evaluate().isEmpty,
        );
        expect(api.posts, [original, original]);
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
        await tester.runAsync(() => folder.delete(recursive: true));
        await tester.binding.setSurfaceSize(null);
      }
    },
  );

  testWidgets(
    'local durable write failure sends no POST and keeps the form editable',
    (tester) async {
      final folder = (await tester.runAsync(
        () => Directory.systemTemp.createTemp('journal-full-'),
      ))!;
      final api = DurableCreateApi();
      try {
        await loginJournal(
          tester,
          api,
          ProjectCreationJournal(device: FailingDevice(folder)),
        );
        await enterDurable(tester);
        await tester.tap(find.widgetWithText(FilledButton, 'Anlegen'));
        await until(
          tester,
          () => find
              .textContaining('nicht dauerhaft gespeichert')
              .evaluate()
              .isNotEmpty,
        );
        expect(api.posts, isEmpty);
        expect(
          tester
              .widget<TextFormField>(find.byType(TextFormField).first)
              .enabled,
          isTrue,
        );
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
        await tester.runAsync(() => folder.delete(recursive: true));
        await tester.binding.setSurfaceSize(null);
      }
    },
  );

  testWidgets(
    'current role loss blocks reopening private pending customer data',
    (tester) async {
      final folder = (await tester.runAsync(
        () => Directory.systemTemp.createTemp('journal-role-'),
      ))!;
      final device = JournalDevice(folder),
          api = DurableCreateApi()
            ..rejectNext = const ApiException(0, 'Synthetic missing ACK');
      try {
        await loginJournal(tester, api, ProjectCreationJournal(device: device));
        await enterDurable(tester);
        await tester.tap(find.widgetWithText(FilledButton, 'Anlegen'));
        await until(
          tester,
          () => find.text('Synthetic missing ACK').evaluate().isNotEmpty,
        );
        await tester.tap(find.text('Später fortsetzen'));
        await tester.pumpAndSettle();
        api.currentRole = 'technician';
        await tester.tap(find.widgetWithText(FilledButton, 'Projekt anlegen'));
        await tester.pumpAndSettle();
        expect(find.byType(ProjectDialog), findsNothing);
        expect(find.textContaining('aktuelle Berechtigung'), findsOneWidget);
        expect(find.textContaining('Bestehender Kunde'), findsNothing);
        expect(api.posts, hasLength(1));
      } finally {
        await tester.pumpWidget(const SizedBox());
        api.dispose();
        await tester.runAsync(() => folder.delete(recursive: true));
        await tester.binding.setSurfaceSize(null);
      }
    },
  );
}

import 'dart:convert';

import 'package:cryptography/cryptography.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_payroll.dart';
import 'business_travel_allowances.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart'
    show exportMailAttachment, safeAttachmentFilename;

const personnelStatuses = {
  'draft': 'Entwurf',
  'submitted': 'Eingereicht',
  'approved': 'Freigegeben',
  'rejected': 'Zurückgewiesen',
  'reimbursed': 'Erstattet',
  'reversed': 'Zurückgezahlt',
  'preparation_closed': 'Vorbereitung abgeschlossen',
};
int personnelMinor(Object? input) {
  final value = '$input'.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,11}(?:\.\d{1,2})?$').hasMatch(value))
    throw const FormatException(
      'EUR-Betrag mit höchstens zwei Nachkommastellen eingeben.',
    );
  final parts = value.split('.');
  final result =
      int.parse(parts[0]) * 100 +
      int.parse((parts.length == 2 ? parts[1] : '').padRight(2, '0'));
  if (result < 1 || result > 1000000000000)
    throw const FormatException(
      'Einen positiven Betrag bis 10 Milliarden EUR eingeben.',
    );
  return result;
}

String _amount(Object? minor) {
  final value = minor is int ? minor : 0;
  return '${value ~/ 100}.${(value % 100).toString().padLeft(2, '0')}';
}

String _money(Object? minor) => businessMoney(_amount(minor));
String _hours(Object? seconds) {
  final value = seconds is int ? seconds : 0;
  return '${value ~/ 3600}:${((value % 3600) ~/ 60).toString().padLeft(2, '0')} Std.';
}

String _today() => DateTime.now().toIso8601String().substring(0, 10);
String _hash(List<int> bytes) =>
    bytes.map((value) => value.toRadixString(16).padLeft(2, '0')).join();
Map<String, dynamic> personnelExpenseValues(
  String employeeId,
  Map<String, dynamic> values,
  List<Map<String, dynamic>> items, {
  Map<String, dynamic>? previous,
}) {
  if (items.isEmpty || items.length > 100)
    throw const FormatException('Eine bis 100 belegte Auslagen erfassen.');
  if (previous != null && '${values['correction_reason'] ?? ''}'.trim().isEmpty)
    throw const FormatException('Korrekturgrund angeben.');
  return {
    'employee_id': employeeId,
    'revision': previous?['revision'] ?? 0,
    'purpose': values['purpose'],
    'start_date': values['start_date'],
    'end_date': values['end_date'],
    'items': [
      for (final item in items)
        {
          'date': item['date'],
          'description': item['description'],
          'amount_minor': personnelMinor(item['amount']),
          'currency': 'EUR',
          'receipt_file_id': item['receipt_file_id'],
          if ('${item['project_id'] ?? ''}'.isNotEmpty)
            'project_id': item['project_id'],
        },
    ],
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': values['correction_reason'],
    },
  };
}

Map<String, dynamic> personnelCloseValues(
  String employeeId,
  Map<String, dynamic> preview,
  Map<String, dynamic> values, {
  Map<String, dynamic>? previous,
}) {
  final snapshot = businessMap(preview['snapshot']);
  if (businessMap(snapshot['employee'])['id'] != employeeId ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${preview['source_hash']}'))
    throw const FormatException(
      'Die Vorschau gehört nicht zum gewählten Mitarbeiter.',
    );
  if (values['completeness_confirmed'] != true)
    throw const FormatException(
      'Vollständigkeit der geprüften Monatsquellen ausdrücklich bestätigen.',
    );
  if (previous != null &&
      (previous['employee_id'] != employeeId ||
          previous['month'] != snapshot['month'] ||
          '${values['correction_reason'] ?? ''}'.trim().isEmpty))
    throw const FormatException(
      'Passende Monatsfassung und Korrekturgrund erforderlich.',
    );
  return {
    'employee_id': employeeId,
    'month': snapshot['month'],
    'source_hash': preview['source_hash'],
    'revision': previous?['revision'] ?? 0,
    'completeness_confirmed': true,
    if (previous != null) ...{
      'id': previous['id'],
      'correction_reason': values['correction_reason'],
    },
  };
}

class _PendingPersonnel {
  final entries = <String, ({String employee, String title})>{};
}

final _pendingPersonnel = Expando<_PendingPersonnel>();

class BusinessPersonnelWorkflowPage extends StatefulWidget {
  const BusinessPersonnelWorkflowPage({
    super.key,
    required this.session,
    this.pickFile,
  });
  final BusinessSession session;
  final Future<XFile?> Function()? pickFile;
  @override
  State<BusinessPersonnelWorkflowPage> createState() =>
      _BusinessPersonnelWorkflowPageState();
}

class _BusinessPersonnelWorkflowPageState
    extends State<BusinessPersonnelWorkflowPage> {
  List<Map<String, dynamic>> employees = [],
      files = [],
      agreements = [],
      expenses = [],
      preparations = [];
  Map<String, dynamic>? employee;
  String? userId, error;
  bool busy = false;
  int epoch = 0;
  MailAttachmentPreviewController? previewController;
  String? previewFileId;
  BusinessSession get session => widget.session;
  _PendingPersonnel get retained =>
      _pendingPersonnel[session] ??= _PendingPersonnel();
  bool get available =>
      session.projectId == null &&
      session.hasFeature('personnel_preparation') &&
      (session.can('personnel.read') || session.can('time.own'));
  bool canRead(Map<String, dynamic> person) =>
      available &&
      (session.can('personnel.read') ||
          (person['user_id'] == userId && session.can('time.own')));
  bool write(
    Map<String, dynamic> person, {
    String permission = 'personnel.write',
    bool own = false,
  }) =>
      canRead(person) &&
      session.sectionEnabled('personnel') &&
      (session.canWrite(permission) ||
          (own && person['user_id'] == userId && session.canWrite('time.own')));
  bool fileAllowed(Map<String, dynamic> person, Map<String, dynamic> file) =>
      canRead(person) &&
      (session.can('personnel.read') ||
          file['owner_visible'] == 1 ||
          file['owner_visible'] == true);
  @override
  void initState() {
    super.initState();
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    epoch++;
    session.removeListener(changed);
    previewController?.revoke();
    super.dispose();
  }

  void changed() {
    if (!mounted) return;
    if (!available || employee != null && !canRead(employee!)) {
      epoch++;
      employee = null;
      files = [];
      agreements = [];
      expenses = [];
      preparations = [];
      employees = [];
      previewController?.revoke();
      busy = false;
    } else if (!session.can('personnel.read')) {
      files = files
          .where(
            (file) =>
                file['owner_visible'] == 1 || file['owner_visible'] == true,
          )
          .toList();
      employees = employees
          .where((person) => person['user_id'] == userId)
          .toList();
      if (previewFileId != null &&
          !files.any((file) => file['id'] == previewFileId))
        previewController?.revoke();
    }
    if (!session.allowed) retained.entries.clear();
    setState(() {});
  }

  void guard(
    Map<String, dynamic> person, {
    String? permission,
    bool own = false,
  }) {
    if (!mounted ||
        !canRead(person) ||
        (permission != null &&
            !write(person, permission: permission, own: own)))
      throw const ApiException(403, 'Die aktuelle Personalberechtigung fehlt.');
  }

  Future<void> load({String? selected}) async {
    if (!available) return;
    final captured = ++epoch;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final user = businessMap(await session.api.call('/api/me'));
      final team = businessItems(await session.read('/employees'));
      if (!mounted || captured != epoch || !available) return;
      userId = '${user['id']}';
      employees = team.where(canRead).toList();
      final chosen =
          employees
              .where((p) => p['id'] == (selected ?? employee?['id']))
              .firstOrNull ??
          employees.where((p) => p['user_id'] == userId).firstOrNull ??
          employees.firstOrNull;
      if (chosen == null) {
        setState(() => employee = null);
        return;
      }
      employee = chosen;
      final query = Uri(queryParameters: {'employee_id': '${chosen['id']}'})
          .query;
      final results = await Future.wait(
        [
          'files',
          'agreements',
          'expenses',
          'payroll-preparations',
        ].map((kind) => session.read('/personnel/$kind?$query')),
      );
      if (!mounted || captured != epoch || !canRead(chosen)) return;
      for (final value in results) {
        if (businessMap(value)['employee_id'] != chosen['id'])
          throw const ApiException(
            0,
            'Die Personalantwort gehört zu einem anderen Mitarbeiter.',
          );
      }
      setState(() {
        files = businessItems(businessMap(results[0])['items']);
        agreements = businessItems(businessMap(results[1])['items']);
        expenses = businessItems(businessMap(results[2])['items']);
        preparations = businessItems(businessMap(results[3])['items']);
      });
    } catch (e) {
      if (mounted && captured == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && captured == epoch) setState(() => busy = false);
    }
  }

  Future<void> command(
    Map<String, dynamic> person,
    String key,
    String path,
    Map<String, dynamic> values,
    String title, {
    String permission = 'personnel.write',
    bool own = false,
  }) async {
    guard(person, permission: permission, own: own);
    retained.entries[key] = (employee: '${person['id']}', title: title);
    if (session.pending(key)) {
      await session.repeatPersonnelCommand(key);
    } else {
      await session.command(key, path, values);
    }
    if (!session.pending(key)) retained.entries.remove(key);
  }

  Future<void> repeat(String key, Map<String, dynamic> person) async {
    guard(person);
    setState(() => busy = true);
    try {
      await session.repeatPersonnelCommand(key);
      retained.entries.remove(key);
      await load(selected: '${person['id']}');
    } catch (e) {
      if (mounted && canRead(person)) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> editor(
    Map<String, dynamic> person,
    String title,
    String key,
    String path,
    List<BusinessField> fields,
    Map<String, dynamic> Function(Map<String, dynamic>) values, {
    String permission = 'personnel.write',
    bool own = false,
  }) async {
    guard(person, permission: permission, own: own);
    await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => BusinessEditor(
        session: session,
        title: title,
        fields: fields,
        pendingKey: key,
        readAllowed: () => canRead(person),
        writePermission: session.canWrite(permission)
            ? permission
            : own
            ? 'time.own'
            : permission,
        saveLabel: title,
        onSave: (input) async {
          guard(person, permission: permission, own: own);
          await command(
            person,
            key,
            path,
            session.pendingCommandValues(key, path: path) ?? values(input),
            title,
            permission: permission,
            own: own,
          );
        },
      ),
    );
    if (mounted && canRead(person)) await load(selected: '${person['id']}');
  }

  Future<void> upload(
    Map<String, dynamic> person,
    String purpose, [
    Map<String, dynamic>? previous,
  ]) async {
    guard(person, own: purpose == 'expense_receipt');
    final captured = epoch;
    try {
      final file =
          await (widget.pickFile?.call() ??
              openFile(
                acceptedTypeGroups: [
                  const XTypeGroup(
                    label: 'Personaloriginal',
                    extensions: ['pdf', 'png', 'jpg', 'jpeg'],
                    uniformTypeIdentifiers: [
                      'com.adobe.pdf',
                      'public.png',
                      'public.jpeg',
                    ],
                  ),
                ],
              ));
      if (file == null || !mounted || captured != epoch) return;
      guard(person, own: purpose == 'expense_receipt');
      final length = await file.length();
      if (length < 1 || length > 600000)
        throw const ApiException(
          413,
          'Ein PDF-, PNG- oder JPEG-Original bis 600 kB auswählen.',
        );
      final bytes = await file.readAsBytes();
      if (bytes.length != length)
        throw const ApiException(
          409,
          'Das Original wurde während der Auswahl geändert.',
        );
      String? type;
      if (bytes.length >= 5 &&
          ascii.decode(bytes.sublist(0, 5), allowInvalid: true) == '%PDF-')
        type = 'application/pdf';
      if (bytes.length >= 8 &&
          base64Encode(bytes.sublist(0, 8)) == 'iVBORw0KGgo=')
        type = 'image/png';
      if (bytes.length >= 3 &&
          bytes[0] == 255 &&
          bytes[1] == 216 &&
          bytes[2] == 255)
        type = 'image/jpeg';
      if (type == null)
        throw const ApiException(415, 'PDF, PNG oder JPEG erwartet.');
      if (!mounted || captured != epoch) return;
      await editor(
        person,
        'Original unverändert speichern',
        'personnel-file-${person['id']}-$purpose-${previous?['id'] ?? 'new'}',
        '/personnel/files',
        [
          if (purpose == 'personnel')
            const BusinessField(
              'owner_visible',
              'Für den Mitarbeiter sichtbar',
              type: BusinessInput.toggle,
              initial: false,
            ),
        ],
        (values) => {
          'employee_id': person['id'],
          'purpose': purpose,
          'owner_visible':
              purpose == 'expense_receipt' || values['owner_visible'] == true,
          'filename': safeAttachmentFilename(file.name),
          'media_type': type,
          'content_base64': base64Encode(bytes),
          if (previous != null) 'supersedes': previous['id'],
        },
        own: purpose == 'expense_receipt',
      );
    } catch (e) {
      if (mounted && canRead(person)) setState(() => error = '$e');
    }
  }

  Future<void> fileView(
    Map<String, dynamic> person,
    Map<String, dynamic> file,
  ) async {
    guard(person);
    if (!fileAllowed(person, file)) return;
    final captured = epoch;
    try {
      final bytes = await session.api.bytes(
        session.path('/personnel/files/${file['id']}/content'),
        mediaType: '${file['media_type']}',
      );
      final sha = _hash((await Sha256().hash(bytes)).bytes);
      if (!mounted || captured != epoch || !fileAllowed(person, file)) return;
      if (sha != file['sha256'] || bytes.length != file['size'])
        throw const ApiException(
          0,
          'Die Originaldatei stimmt nicht mit der gespeicherten Prüfsumme überein.',
        );
      final controller = MailAttachmentPreviewController(
        VerifiedMailAttachment(
          bytes: bytes,
          filename: '${file['filename']}',
          mediaType: '${file['media_type']}',
          sha256: sha,
        ),
      );
      previewController = controller;
      previewFileId = '${file['id']}';
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => MailAttachmentPreviewPage(
            controller: controller,
            mayView: () =>
                mounted && captured == epoch && fileAllowed(person, file),
            exporter: exportMailAttachment,
          ),
        ),
      );
      if (previewController == controller) {
        previewController = null;
        previewFileId = null;
      }
      controller.dispose();
    } catch (e) {
      if (mounted && canRead(person)) setState(() => error = '$e');
    }
  }

  Future<void> agreement(
    Map<String, dynamic> person, [
    Map<String, dynamic>? previous,
  ]) async {
    final choices = {
      for (final file in files.where((file) => file['purpose'] == 'personnel'))
        '${file['id']}': '${file['filename']}',
    };
    if (choices.isEmpty) {
      setState(
        () => error = 'Zuerst das Original der Entgeltvereinbarung in die Personalakte hochladen.',
      );
      return;
    }
    await editor(
      person,
      previous == null
          ? 'Vereinbarung belegt speichern'
          : 'Entgeltvereinbarung korrigieren',
      'personnel-agreement-${person['id']}-${previous?['id'] ?? 'new'}-${previous?['revision'] ?? 0}',
      '/personnel/agreements',
      [
        BusinessField(
          'effective_from',
          'Gültig ab',
          type: BusinessInput.date,
          required: true,
          initial: previous?['effective_from'] ?? _today(),
        ),
        BusinessField(
          'employment_kind',
          'Beschäftigungsart',
          type: BusinessInput.choice,
          required: true,
          initial: previous?['employment_kind'] ?? 'regular',
          choices: const {
            'regular': 'Reguläre Beschäftigung',
            'minijob': 'Minijob',
          },
        ),
        BusinessField(
          'pay_basis',
          'Entgeltbasis',
          type: BusinessInput.choice,
          required: true,
          initial: previous?['pay_basis'] ?? 'monthly',
          choices: const {'monthly': 'Monatlich', 'hourly': 'Je Stunde'},
        ),
        BusinessField(
          'amount',
          'Vereinbarter Bruttobetrag EUR',
          required: true,
          initial: previous == null ? '' : _amount(previous['amount_minor']),
        ),
        BusinessField(
          'reference_file_id',
          'Original der Entgeltvereinbarung',
          type: BusinessInput.choice,
          required: true,
          initial: previous?['reference_file_id'],
          choices: choices,
        ),
        BusinessField(
          'notes',
          'Vertragsnotiz',
          type: BusinessInput.multiline,
          initial: previous?['notes'] ?? '',
        ),
        if (previous != null)
          const BusinessField(
            'correction_reason',
            'Korrekturgrund',
            type: BusinessInput.multiline,
            required: true,
          ),
      ],
      (values) => {
        'employee_id': person['id'],
        'revision': previous?['revision'] ?? 0,
        for (final key in [
          'effective_from',
          'employment_kind',
          'pay_basis',
          'reference_file_id',
          'notes',
          'correction_reason',
        ])
          if (values.containsKey(key)) key: values[key],
        'amount_minor': personnelMinor(values['amount']),
        'currency': 'EUR',
        if (previous != null) 'id': previous['id'],
      },
    );
  }

  Future<void> expense(
    Map<String, dynamic> person, [
    Map<String, dynamic>? previous,
  ]) async {
    guard(person, own: true);
    final receipts = {
      for (final file in files.where(
        (file) => file['purpose'] == 'expense_receipt',
      ))
        '${file['id']}': '${file['filename']}',
    };
    if (receipts.isEmpty) {
      setState(
        () => error = 'Zuerst die tatsächlichen Auslagenbelege hochladen.',
      );
      return;
    }
    final key =
        'personnel-expense-${person['id']}-${previous?['id'] ?? 'new'}-${previous?['revision'] ?? 0}';
    final pending = session.pendingCommandValues(
      key,
      path: '/personnel/expenses',
    );
    int count = businessItems(pending?['items'] ?? previous?['items'] ?? [])
        .length;
    if (count < 1) count = 1;
    if (pending == null) {
      final selected = await showDialog<int>(
        context: context,
        builder: (_) => _ExpenseCount(initial: count),
      );
      if (selected == null || !mounted) return;
      count = selected;
    }
    final old = businessItems(previous?['items'] ?? []),
        fields = <BusinessField>[
          BusinessField(
            'purpose',
            'Reisezweck',
            type: BusinessInput.multiline,
            required: true,
            initial: previous?['purpose'] ?? '',
          ),
          BusinessField(
            'start_date',
            'Reisebeginn',
            type: BusinessInput.date,
            required: true,
            initial: previous?['start_date'] ?? _today(),
          ),
          BusinessField(
            'end_date',
            'Reiseende',
            type: BusinessInput.date,
            required: true,
            initial: previous?['end_date'] ?? _today(),
          ),
        ];
    for (var index = 0; index < count; index++) {
      final item = index < old.length ? old[index] : <String, dynamic>{},
          number = index + 1;
      fields.addAll([
        BusinessField(
          'date_$index',
          'Belegdatum $number',
          type: BusinessInput.date,
          required: true,
          initial: item['date'] ?? _today(),
        ),
        BusinessField(
          'description_$index',
          'Auslage $number',
          required: true,
          initial: item['description'] ?? '',
        ),
        BusinessField(
          'amount_$index',
          'Tatsächlicher Betrag EUR $number',
          required: true,
          initial: item.containsKey('amount_minor')
              ? _amount(item['amount_minor'])
              : '',
        ),
        BusinessField(
          'receipt_file_id_$index',
          'Belegoriginal $number',
          type: BusinessInput.choice,
          required: true,
          choices: receipts,
          initial: item['receipt_file_id'],
        ),
        BusinessField(
          'project_id_$index',
          'Projektzuordnung $number',
          type: BusinessInput.choice,
          initial: item['project_id'] ?? '',
          choices: {
            '': 'Ohne Projektzuordnung',
            for (final project in session.projects)
              '${project['id']}': '${project['name']}',
          },
        ),
      ]);
    }
    if (previous != null)
      fields.add(
        const BusinessField(
          'correction_reason',
          'Korrekturgrund',
          type: BusinessInput.multiline,
          required: true,
        ),
      );
    await editor(
      person,
      'Antrag als Entwurf speichern',
      key,
      '/personnel/expenses',
      fields,
      (values) => personnelExpenseValues('${person['id']}', values, [
        for (var index = 0; index < count; index)
          {
            for (final field in [
              'date',
              'description',
              'amount',
              'receipt_file_id',
              'project_id',
            ])
              field: values['${field}_$index'],
          },
      ], previous: previous),
      own: true,
    );
  }

  Future<void> expenseAction(
    Map<String, dynamic> person,
    Map<String, dynamic> item,
    String operation,
  ) async {
    final submit = operation == 'submit',
        payment = ['reimburse', 'reverse-reimbursement'].contains(operation),
        title = {
          'submit': 'Reisekosten einreichen',
          'approve': 'Reisekosten freigeben',
          'reject': 'Reisekosten zurückweisen',
          'reimburse': 'Erstattung bestätigen',
          'reverse-reimbursement': 'Rückzahlung bestätigen',
        }[operation]!;
    await editor(
      person,
      title,
      'personnel-${item['id']}-$operation-${item['revision']}',
      '/personnel/expenses/${item['id']}/$operation',
      [
        if (payment) ...[
          BusinessField(
            'paid_on',
            'Tatsächlicher Zahlungstag',
            type: BusinessInput.date,
            required: true,
            initial: _today(),
          ),
          const BusinessField(
            'payment_reference',
            'Zahlungsnachweis / Referenz',
            required: true,
          ),
          BusinessField(
            'confirmed',
            'Ich bestätige die bereits ausgeführte vollständige ${operation == 'reimburse' ? 'Erstattung' : 'Rückzahlung'} von ${_money(item['total_minor'])}.',
            type: BusinessInput.toggle,
            initial: false,
          ),
        ] else if (!submit)
          const BusinessField(
            'reason',
            'Prüfvermerk',
            type: BusinessInput.multiline,
            required: true,
          ),
      ],
      (values) {
        if (payment && values['confirmed'] != true)
          throw const FormatException(
            'Tatsächlich ausgeführte Zahlung ausdrücklich bestätigen.',
          );
        return {
          'revision': item['revision'],
          ...values,
          if (payment) 'amount_minor': item['total_minor'],
        };
      },
      permission: submit ? 'personnel.write' : 'personnel.approve',
      own: submit,
    );
  }

  Future<void> month(
    Map<String, dynamic> person, [
    Map<String, dynamic>? previous,
  ]) async {
    guard(person);
    if (!session.can('personnel.read')) return;
    String? selected;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: session,
        title: 'Monatsquellen auswählen',
        readPermission: 'personnel.read',
        readAllowed: () => canRead(person),
        fields: [
          BusinessField(
            'month',
            'Abrechnungsmonat JJJJ-MM',
            required: true,
            initial: previous?['month'] ?? _today().substring(0, 7),
          ),
        ],
        saveLabel: 'Monatsquellen laden',
        onSave: (values) async {
          if (!RegExp(r'^20\d{2}-(0[1-9]|1[0-2])$')
              .hasMatch('${values['month']}'))
            throw const FormatException('Monat als JJJJ-MM eingeben.');
          selected = '${values['month']}';
        },
      ),
    );
    if (selected == null || !mounted) return;
    final captured = epoch;
    try {
      final value = businessMap(
        await session.read(
          '/personnel/payroll-preparations/preview?${Uri(queryParameters: {'employee_id': '${person['id']}', 'month': selected!}).query}',
        ),
      );
      if (!mounted ||
          captured != epoch ||
          !canRead(person) ||
          !session.can('personnel.read'))
        return;
      await details(
        person,
        'Monatsquellen prüfen',
        snapshot(person, businessMap(value['snapshot'])),
        extra: write(person, permission: 'personnel.approve')
            ? [
                FilledButton(
                  onPressed: () async {
                    Navigator.pop(context);
                    await editor(
                      person,
                      'Lohnvorbereitung abschließen',
                      'personnel-month-${person['id']}-$selected-${previous?['revision'] ?? 0}',
                      '/personnel/payroll-preparations',
                      [
                        const BusinessField(
                          'completeness_confirmed',
                          'Ich habe Vereinbarungen, Zeiten, Abwesenheiten und Auslagen geprüft und bestätige die Vollständigkeit der Monatsquellen.',
                          type: BusinessInput.toggle,
                          initial: false,
                        ),
                        if (previous != null)
                          const BusinessField(
                            'correction_reason',
                            'Korrekturgrund',
                            type: BusinessInput.multiline,
                            required: true,
                          ),
                      ],
                      (values) => personnelCloseValues(
                        '${person['id']}',
                        value,
                        values,
                        previous: previous,
                      ),
                      permission: 'personnel.approve',
                    );
                  },
                  child: const Text('Geprüfte Quellen bestätigen'),
                ),
              ]
            : [],
      );
    } catch (e) {
      if (mounted && canRead(person)) setState(() => error = '$e');
    }
  }

  Widget? originalButton(Map<String, dynamic> person, Object? id) {
    final file = files.where((row) => row['id'] == id).firstOrNull;
    return file == null
        ? null
        : TextButton(
            onPressed: () => fileView(person, file),
            child: const Text('Original'),
          );
  }

  List<Widget> expenseDetails(
    Map<String, dynamic> person,
    Map<String, dynamic> item,
  ) => [
    Text(
      '${item['purpose']} · ${personnelStatuses[item['status']] ?? item['status']} · ${_money(item['total_minor'])}',
      style: Theme.of(context).textTheme.titleMedium,
    ),
    for (final line in businessItems(item['items']))
      ListTile(
        contentPadding: EdgeInsets.zero,
        title: Text('${line['description']}'),
        subtitle: Text(
          '${businessDate(line['date'])} · ${_money(line['amount_minor'])}',
        ),
        trailing: originalButton(person, line['receipt_file_id']),
      ),
    if (item['decision'] != null)
      Text('Prüfvermerk: ${item['decision']['reason']}'),
    for (final payment in businessItems(item['payments']))
      Text(
        '${payment['kind'] == 'reimbursement' ? 'Erstattung' : 'Rückzahlung'} · ${businessDate(payment['paid_on'])} · ${_money(payment['amount_minor'])} · ${payment['reference']}',
      ),
    if ('${item['correction_reason'] ?? ''}'.isNotEmpty)
      Text('Korrektur: ${item['correction_reason']}'),
  ];
  List<Widget> snapshot(
    Map<String, dynamic> person,
    Map<String, dynamic> value,
  ) => [
    const Notice(
      'Erfasste und freigegebene Quellen. Vollständigkeit fachlich prüfen; fehlende Erfassungen werden nicht automatisch erkannt.',
    ),
    Text(
      'Monat ${value['month']} · ${_hours(value['net_work_seconds'])} freigegebene Arbeitszeit · ${_money(value['recorded_expenses_minor'])} erfasste Auslagen',
    ),
    const Divider(),
    const Text('Belegte Entgeltvereinbarungen'),
    for (final item in businessItems(value['agreements']))
      ...agreementDetails(person, item),
    const Divider(),
    const Text('Freigegebene Arbeitstage'),
    for (final day in businessItems(value['approved_days']))
      Text(
        '${businessDate(day['date'])} · ${_hours(day['net_seconds'])} · Fassung ${day['revision']}',
      ),
    const Divider(),
    const Text('Freigegebene Abwesenheiten'),
    for (final item in businessItems(value['approved_absences']))
      Text(
        '${businessDate(item['start_date'])} – ${businessDate(item['end_date'])} · ${{'vacation': 'Urlaub', 'sick': 'Krankheit', 'other': 'Sonstige Abwesenheit'}[item['kind']] ?? item['kind']}',
      ),
    const Divider(),
    const Text('Belegte Reisen und Erstattungen'),
    for (final item in businessItems(value['expenses']))
      ...expenseDetails(person, item),
  ];
  List<Widget> agreementDetails(
    Map<String, dynamic> person,
    Map<String, dynamic> item,
  ) => [
    Text(
      'Ab ${businessDate(item['effective_from'])} · ${item['employment_kind'] == 'minijob' ? 'Minijob' : 'Reguläre Beschäftigung'} · ${_money(item['amount_minor'])} ${item['pay_basis'] == 'hourly' ? 'je Stunde' : 'monatlich'} · Fassung ${item['revision']}',
    ),
    if ('${item['notes'] ?? ''}'.isNotEmpty) Text('${item['notes']}'),
    if ('${item['correction_reason'] ?? ''}'.isNotEmpty)
      Text('Korrektur: ${item['correction_reason']}'),
    if (files
            .where((file) => file['id'] == item['reference_file_id'])
            .firstOrNull
        case final file?)
      TextButton(
        onPressed: () => fileView(person, file),
        child: const Text('Vertragsoriginal öffnen'),
      ),
  ];
  Future<void> details(
    Map<String, dynamic> person,
    String title,
    List<Widget> children, {
    List<Widget> extra = const [],
  }) async {
    guard(person);
    final private = session.can('personnel.read');
    bool visible() =>
        canRead(person) && (!private || session.can('personnel.read'));
    await showDialog<void>(
      context: context,
      builder: (_) => ListenableBuilder(
        listenable: session,
        builder: (context, _) => AlertDialog(
          title: Text(title),
          content: SizedBox(
            width: 760,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: visible()
                    ? children
                    : [const Text('Die Personalberechtigung wurde entzogen.')],
              ),
            ),
          ),
          actions: [
            if (visible()) ...extra,
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Schließen'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> history(
    Map<String, dynamic> person,
    String collection,
    Map<String, dynamic> item,
  ) async {
    guard(person);
    final captured = epoch;
    try {
      final result = businessMap(
        await session.read('/personnel/$collection/${item['id']}/history'),
      );
      if (!mounted || captured != epoch || !canRead(person)) return;
      await details(
        person,
        'Historie · ${item['month'] ?? item['purpose'] ?? 'Entgeltvereinbarung'}',
        [
          for (final record in businessItems(result['items'])) ...[
            Text(
              'Fassung ${record['revision']} · ${businessDate(record['created_at'], time: true)}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (collection == 'expenses')
              ...expenseDetails(person, record)
            else if (collection == 'agreements')
              ...agreementDetails(person, record)
            else ...[
              ...snapshot(person, businessMap(record['snapshot'])),
              if ('${record['correction_reason'] ?? ''}'.isNotEmpty)
                Text('Korrektur: ${record['correction_reason']}'),
              ListenableBuilder(
                listenable: session,
                builder: (context, _) =>
                    session.can('personnel.read') &&
                        session.can('personnel.export')
                    ? Wrap(
                        spacing: 8,
                        children: [
                          for (final type in ['pdf', 'csv', 'json'])
                            TextButton(
                              onPressed: () => export(person, record, type),
                              child: Text(
                                '${type.toUpperCase()} · Fassung ${record['revision']}',
                              ),
                            ),
                        ],
                      )
                    : const SizedBox.shrink(),
              ),
            ],
            const Divider(),
          ],
        ],
      );
    } catch (e) {
      if (mounted && canRead(person)) setState(() => error = '$e');
    }
  }

  Future<void> export(
    Map<String, dynamic> person,
    Map<String, dynamic> record,
    String type,
  ) async {
    guard(person);
    bool allowed() =>
        mounted &&
        canRead(person) &&
        session.can('personnel.read') &&
        session.can('personnel.export');
    if (!allowed()) return;
    try {
      final media = {
        'pdf': 'application/pdf',
        'csv': 'text/csv',
        'json': 'application/json',
      }[type]!;
      final bytes = await session.api.bytes(
        session.path(
          '/personnel/payroll-preparations/${record['id']}/$type?revision=${record['revision']}',
        ),
        mediaType: media,
      );
      final sha = _hash((await Sha256().hash(bytes)).bytes);
      if (!allowed()) return;
      if (type == 'pdf' && sha != record['pdf_sha256'])
        throw const ApiException(
          0,
          'Das Monats-PDF stimmt nicht mit der archivierten Prüfsumme überein.',
        );
      await exportMailAttachment(
        context,
        VerifiedMailAttachment(
          bytes: bytes,
          filename:
              'lohnvorbereitung-${record['month']}-v${record['revision']}.$type',
          mediaType: media,
          sha256: sha,
        ),
        allowed,
      );
    } catch (e) {
      if (allowed()) setState(() => error = '$e');
    }
  }

  Widget section(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final person = employee;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Personalakte, Reisen und Lohnvorbereitung'),
        actions: [
          IconButton(
            onPressed: busy ? null : load,
            tooltip: 'Aktualisieren',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: !available
          ? const BusinessEmpty(
              'Personalbereich nicht freigegeben',
              'Die aktuellen Personalrechte bestimmen die sichtbaren Daten.',
            )
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const Notice(
                  'Belegte Vereinbarungen, Reisen und Monatsquellen. Keine Nettolohn-, Steuer-, Sozialabgaben- oder Pauschalenberechnung.',
                ),
                if (error != null) Notice(error!, error: true),
                if (busy) const LinearProgressIndicator(),
                if (employees.isNotEmpty)
                  DropdownButtonFormField<String>(
                    initialValue: person?['id'],
                    decoration: const InputDecoration(labelText: 'Mitarbeiter'),
                    items: [
                      for (final value in employees)
                        DropdownMenuItem(
                          value: '${value['id']}',
                          child: Text('${value['name']}'),
                        ),
                    ],
                    onChanged: busy ? null : (value) => load(selected: value),
                  ),
                if (person == null && !busy)
                  const BusinessEmpty(
                    'Mitarbeiterprofil fehlt',
                    'Zuerst das Mitarbeiterprofil mit einem vorhandenen Benutzer verbinden.',
                  ),
                if (person != null && canRead(person)) ...[
                  if (travelAvailable(session))
                    Align(
                      alignment: Alignment.centerLeft,
                      child: FilledButton.icon(
                        onPressed: busy
                            ? null
                            : () async {
                                await Navigator.push<void>(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) =>
                                        BusinessTravelAllowancesPage(
                                          session: session,
                                          employee: person,
                                        ),
                                  ),
                                );
                                if (mounted) await load(selected: person['id']);
                              },
                        icon: const Icon(Icons.luggage_outlined),
                        label: const Text('Reisen und Pauschalen'),
                      ),
                    ),
                  if (payrollAvailable(session))
                    Align(
                      alignment: Alignment.centerLeft,
                      child: FilledButton.icon(
                        onPressed: () async {
                          await Navigator.push<void>(
                            context,
                            MaterialPageRoute(
                              builder: (_) => BusinessPayrollPage(
                                session: session,
                                employee: person,
                              ),
                            ),
                          );
                          if (mounted) await load(selected: person['id']);
                        },
                        icon: const Icon(Icons.calculate_outlined),
                        label: const Text('Lohnberechnung 2026'),
                      ),
                    ),
                  for (final entry in retained.entries.entries.where(
                    (entry) =>
                        entry.value.employee == person['id'] &&
                        session.pending(entry.key),
                  ))
                    Card(
                      child: ListTile(
                        title: Text('Antwort offen: ${entry.value.title}'),
                        subtitle: const Text(
                          'Denselben Vorgang unverändert wiederholen.',
                        ),
                        trailing: TextButton(
                          onPressed: busy
                              ? null
                              : () => repeat(entry.key, person),
                          child: const Text('Unverändert wiederholen'),
                        ),
                      ),
                    ),
                  section('Personalakte und Belege', [
                    Wrap(
                      spacing: 8,
                      children: [
                        if (write(person))
                          FilledButton(
                            onPressed: () => upload(person, 'personnel'),
                            child: const Text('Personaloriginal hochladen'),
                          ),
                        if (write(person, own: true))
                          OutlinedButton(
                            onPressed: () => upload(person, 'expense_receipt'),
                            child: const Text('Auslagenbeleg hochladen'),
                          ),
                      ],
                    ),
                    for (final file in files)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text('${file['filename']}'),
                        subtitle: Text(
                          '${file['purpose'] == 'personnel' ? 'Personalakte' : 'Auslagenbeleg'} · ${file['owner_visible'] == 1 ? 'Für Mitarbeiter sichtbar' : 'Nur Personalverwaltung'}',
                        ),
                        onTap: () => fileView(person, file),
                        trailing:
                            write(
                              person,
                              own: file['purpose'] == 'expense_receipt',
                            )
                            ? IconButton(
                                tooltip: 'Ergänzendes Original',
                                onPressed: () =>
                                    upload(person, '${file['purpose']}', file),
                                icon: const Icon(Icons.add_link),
                              )
                            : null,
                      ),
                  ]),
                  section('Entgeltvereinbarungen', [
                    if (write(person))
                      FilledButton(
                        onPressed: () => agreement(person),
                        child: const Text('Vereinbarung erfassen'),
                      ),
                    for (final item in agreements)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(
                          '${_money(item['amount_minor'])} ${item['pay_basis'] == 'hourly' ? 'je Stunde' : 'monatlich'}',
                        ),
                        subtitle: Text(
                          'Ab ${businessDate(item['effective_from'])} · Fassung ${item['revision']}',
                        ),
                        onTap: () => history(person, 'agreements', item),
                        trailing: write(person)
                            ? TextButton(
                                onPressed: () => agreement(person, item),
                                child: const Text('Korrigieren'),
                              )
                            : null,
                      ),
                  ]),
                  section('Reisen und Auslagen', [
                    if (write(person, own: true))
                      FilledButton(
                        onPressed: () => expense(person),
                        child: const Text('Reisekosten erfassen'),
                      ),
                    for (final item in expenses)
                      Padding(
                        padding: const EdgeInsets.only(top: 14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              title: Text(
                                '${item['purpose']} · ${_money(item['total_minor'])}',
                              ),
                              subtitle: Text(
                                '${personnelStatuses[item['status']]} · Fassung ${item['revision']}',
                              ),
                              onTap: () => history(person, 'expenses', item),
                            ),
                            Wrap(
                              spacing: 8,
                              children: [
                                if ([
                                      'draft',
                                      'rejected',
                                      'approved',
                                      'reversed',
                                    ].contains(item['status']) &&
                                    write(person, own: true))
                                  TextButton(
                                    onPressed: () => expense(person, item),
                                    child: const Text('Antrag korrigieren'),
                                  ),
                                if (item['status'] == 'draft' &&
                                    write(person, own: true))
                                  FilledButton(
                                    onPressed: () =>
                                        expenseAction(person, item, 'submit'),
                                    child: const Text('Einreichen'),
                                  ),
                                if (item['status'] == 'submitted' &&
                                    person['user_id'] != userId &&
                                    item['submitted_by'] != userId &&
                                    write(
                                      person,
                                      permission: 'personnel.approve',
                                    )) ...[
                                  TextButton(
                                    onPressed: () =>
                                        expenseAction(person, item, 'approve'),
                                    child: const Text('Freigeben'),
                                  ),
                                  TextButton(
                                    onPressed: () =>
                                        expenseAction(person, item, 'reject'),
                                    child: const Text('Zurückweisen'),
                                  ),
                                ],
                                if ([
                                      'approved',
                                      'reimbursed',
                                    ].contains(item['status']) &&
                                    write(
                                      person,
                                      permission: 'personnel.approve',
                                    ))
                                  TextButton(
                                    onPressed: () => expenseAction(
                                      person,
                                      item,
                                      item['status'] == 'approved'
                                          ? 'reimburse'
                                          : 'reverse-reimbursement',
                                    ),
                                    child: Text(
                                      item['status'] == 'approved'
                                          ? 'Erstattung bestätigen'
                                          : 'Rückzahlung bestätigen',
                                    ),
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ),
                  ]),
                  section('Monatliche Lohnvorbereitung', [
                    if (session.can('personnel.read'))
                      FilledButton(
                        onPressed: () => month(person),
                        child: const Text('Monatsquellen prüfen'),
                      ),
                    for (final item in preparations)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(
                          '${item['month']} · Fassung ${item['revision']}',
                        ),
                        subtitle: Text(
                          businessDate(item['created_at'], time: true),
                        ),
                        onTap: () =>
                            history(person, 'payroll-preparations', item),
                        trailing:
                            write(person, permission: 'personnel.approve') &&
                                session.can('personnel.read')
                            ? TextButton(
                                onPressed: () => month(person, item),
                                child: const Text('Monat korrigieren'),
                              )
                            : null,
                      ),
                  ]),
                ],
              ],
            ),
    );
  }
}

class _ExpenseCount extends StatefulWidget {
  const _ExpenseCount({required this.initial});
  final int initial;
  @override
  State<_ExpenseCount> createState() => _ExpenseCountState();
}

class _ExpenseCountState extends State<_ExpenseCount> {
  late final controller = TextEditingController(text: '${widget.initial}');
  String? error;
  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Belegte Auslagen'),
    content: TextField(
      controller: controller,
      keyboardType: TextInputType.number,
      decoration: InputDecoration(
        labelText: 'Anzahl der Belege',
        errorText: error,
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(
        onPressed: () {
          final value = int.tryParse(controller.text);
          if (value == null || value < 1 || value > 100) {
            setState(() => error = 'Eine bis 100 Auslagen erfassen.');
            return;
          }
          Navigator.pop(context, value);
        },
        child: const Text('Belegdaten erfassen'),
      ),
    ],
  );
}

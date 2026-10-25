import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:flutter/material.dart';

import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';
import 'mail_attachment_preview.dart';
import 'mail_attachment_widgets.dart' show exportMailAttachment;

const businessContactFields = [
  BusinessField('name', 'Name / Firma', required: true),
  BusinessField(
    'entity_type',
    'Kontaktart',
    type: BusinessInput.choice,
    required: true,
    initial: 'company',
    choices: {'person': 'Privatperson', 'company': 'Unternehmen'},
  ),
  BusinessField(
    'kinds',
    'Beziehung',
    type: BusinessInput.multiple,
    initial: ['customer'],
    choices: {
      'customer': 'Kunde',
      'supplier': 'Lieferant',
      'partner': 'Partner',
    },
  ),
  BusinessField('contact', 'Hauptansprechpartner'),
  BusinessField('email', 'E-Mail'),
  BusinessField('phone', 'Telefon'),
  BusinessField('address', 'Hauptanschrift', type: BusinessInput.multiline),
  BusinessField('notes', 'Interne Notizen', type: BusinessInput.multiline),
  BusinessField('active', 'Aktiv', type: BusinessInput.toggle, initial: true),
];

class BusinessContactsPage extends StatelessWidget {
  const BusinessContactsPage({super.key, required this.session});
  final BusinessSession session;
  Future<void> create(BuildContext context) async {
    String? id;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        readPermission: 'contacts.read',
        writePermission: 'contacts.write',
        session: session,
        title: 'Kontakt erstellen',
        fields: businessContactFields,
        onSave: (values) async {
          final result = businessMap(
            await session.command(
              'contact-create-${values['name']}',
              '/contacts',
              values,
            ),
          );
          id = result['id'];
        },
      ),
    );
    if (context.mounted && session.allowed && id != null)
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => BusinessContactPage(session: session, id: id!),
        ),
      );
  }

  @override
  Widget build(BuildContext context) => BusinessCollection(
    session: session,
    path: '/contacts',
    title: 'Kontakte',
    readPermission: 'contacts.read',
    writePermission: 'contacts.write',
    createLabel: 'Kontakt erstellen',
    fields: businessContactFields,
    titleOf: (r) => '${r['name']}',
    subtitleOf: (r) => [
      r['contact'],
      r['email'],
      r['phone'],
    ].where((s) => s != null && s != '').join(' · '),
    onCreate: () => create(context),
    onOpen: (r) async {
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => BusinessContactPage(session: session, id: r['id']),
        ),
      );
    },
  );
}

class BusinessContactPage extends StatefulWidget {
  const BusinessContactPage({
    super.key,
    required this.session,
    required this.id,
  });
  final BusinessSession session;
  final String id;
  @override
  State<BusinessContactPage> createState() => _BusinessContactPageState();
}

class _BusinessContactPageState extends State<BusinessContactPage> {
  Map<String, dynamic>? contact;
  String? error, notice;
  int epoch = 0;
  bool busy = false;
  bool get allowed => widget.session.can('contacts.read');
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    load();
  }

  void changed() {
    if (mounted) {
      if (!allowed) {
        epoch++;
        contact = null;
      }
      setState(() {});
    }
  }

  @override
  void dispose() {
    epoch++;
    contact = null;
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> load() async {
    final current = ++epoch;
    try {
      final result = businessMap(
        await widget.session.read('/contacts/${widget.id}'),
      );
      if (mounted && current == epoch && allowed)
        setState(() => contact = result);
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    }
  }

  Future<void> save(
    String key,
    Map<String, dynamic> values,
    int revision,
  ) async {
    final result = businessMap(
      await widget.session.command(key, '/contacts/${widget.id}', {
        'revision': revision,
        ...values,
      }),
    );
    if (mounted && allowed) setState(() => contact = result);
  }

  Future<void> editBase() async {
    final record = contact;
    if (record == null) return;
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        readPermission: 'contacts.read',
        writePermission: 'contacts.write',
        session: widget.session,
        title: 'Kontakt bearbeiten',
        fields: businessContactFields,
        initial: record,
        onSave: (values) => save(
          'contact-${widget.id}-${record['revision']}',
          values,
          record['revision'],
        ),
      ),
    );
  }

  Future<void> nested(String kind, [Map<String, dynamic>? item]) async {
    final record = contact;
    if (record == null) return;
    final rows = (record[kind] as List? ?? []).map(businessMap).toList();
    final fields = kind == 'persons'
        ? const [
            BusinessField('name', 'Name', required: true),
            BusinessField('role_label', 'Funktion / Beziehung'),
            BusinessField('email', 'E-Mail'),
            BusinessField('phone', 'Telefon'),
          ]
        : const [
            BusinessField(
              'purpose',
              'Verwendung',
              type: BusinessInput.choice,
              required: true,
              initial: 'billing',
              choices: {
                'billing': 'Rechnungsanschrift',
                'site': 'Baustelle / Objekt',
                'delivery': 'Lieferanschrift',
                'other': 'Weitere Anschrift',
              },
            ),
            BusinessField('label', 'Bezeichnung'),
            BusinessField('street', 'Straße und Hausnummer', required: true),
            BusinessField('postal_code', 'Postleitzahl'),
            BusinessField('city', 'Ort', required: true),
            BusinessField(
              'country',
              'Ländercode',
              required: true,
              initial: 'DE',
            ),
          ];
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        readPermission: 'contacts.read',
        writePermission: 'contacts.write',
        session: widget.session,
        title: kind == 'persons' ? 'Ansprechpartner' : 'Anschrift',
        fields: fields,
        initial: item ?? {},
        onSave: (values) async {
          final next = [...rows];
          final value = {if (item?['id'] != null) 'id': item!['id'], ...values};
          if (item == null)
            next.add(value);
          else
            next[next.indexWhere((r) => r['id'] == item['id'])] = value;
          await save('contact-$kind-${widget.id}-${record['revision']}', {
            kind: next,
          }, record['revision']);
        },
      ),
    );
  }

  Future<void> remove(String kind, Map<String, dynamic> item) async {
    final record = contact;
    if (record == null ||
        !await businessConfirm(
          context,
          title: kind == 'persons'
              ? 'Ansprechpartner entfernen?'
              : 'Anschrift entfernen?',
          message: 'Die Kontaktkarte wird aktualisiert. Bereits festgeschriebene Belege behalten ihre damaligen Anschriften.',
          action: 'Entfernen',
        ) ||
        !mounted)
      return;
    try {
      await save('remove-$kind-${item['id']}-${record['revision']}', {
        kind: (record[kind] as List)
            .map(businessMap)
            .where((r) => r['id'] != item['id'])
            .toList(),
      }, record['revision']);
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> export() async {
    if (busy || !widget.session.can('privacy.manage')) return;
    setState(() => busy = true);
    try {
      final result = businessMap(
        await widget.session.read('/contacts/${widget.id}/export'),
      );
      if (!mounted || !allowed || !widget.session.can('privacy.manage')) return;
      final limitations = (result['limitations'] as List? ?? []).join('\n');
      if (!await businessConfirm(
            context,
            title: 'Prüfexport speichern?',
            message:
                'Dieser Export enthält die tatsächlich erfassten Kontakt-, Projekt- und Anfragetextdaten. Er ist kein vollständiger systemübergreifender Betroffenenexport.\n\n$limitations',
            action: 'Prüfdatei speichern',
          ) ||
          !mounted)
        return;
      final bytes = Uint8List.fromList(
        utf8.encode(const JsonEncoder.withIndent('  ').convert(result)),
      );
      final hash = (await Sha256().hash(bytes)).bytes
          .map((n) => n.toRadixString(16).padLeft(2, '0'))
          .join();
      if (!mounted || !allowed) return;
      await exportMailAttachment(
        context,
        VerifiedMailAttachment(
          bytes: bytes,
          filename: 'kontakt-pruefexport.json',
          mediaType: 'application/json',
          sha256: hash,
        ),
        () => mounted && allowed && widget.session.can('privacy.manage'),
      );
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> erase() async {
    final record = contact;
    if (record == null || busy || !widget.session.canWrite('privacy.manage'))
      return;
    if (!await businessConfirm(
          context,
          title: 'Kontaktlöschung prüfen?',
          message: 'Verknüpfte Vorgänge, historische Belege und nachweispflichtige Kopien können die Löschung blockieren. Der Auftrag prüft diese Grenzen; er verspricht keine Löschung fremder Systeme oder aufbewahrungspflichtiger Belege.',
          action: 'Löschprüfung beauftragen',
        ) ||
        !mounted)
      return;
    setState(() => busy = true);
    try {
      final result = businessMap(
        await widget.session.command(
          'erase-${widget.id}-${record['revision']}',
          '/contacts/${widget.id}/erase',
          {'revision': record['revision'], 'confirmed': true},
        ),
      );
      if (mounted && allowed) {
        setState(
          () => notice = result['status'] == 'erased'
              ? 'Der nachweislich isolierte Kontakt wurde anonymisiert.'
              : 'Der Kontakt wurde nicht gelöscht. Die Prüfung ist blockiert: ${(result['blockers'] as List? ?? []).join('; ')}',
        );
        await load();
      }
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final record = contact;
    final writable = widget.session.canWrite('contacts.write');
    return Scaffold(
      appBar: AppBar(
        title: Text(allowed ? '${record?['name'] ?? 'Kontakt'}' : 'Kontakt'),
      ),
      body: !allowed
          ? const Center(child: Text('Der Zugang ist nicht mehr verfügbar.'))
          : ListView(
              padding: const EdgeInsets.all(24),
              children: [
                if (error != null) Notice(error!, error: true),
                if (notice != null) Notice(notice!),
                if (record != null) ...[
                  Text(
                    '${record['name']}',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 12),
                  for (final field in [
                    'contact',
                    'email',
                    'phone',
                    'address',
                    'notes',
                  ])
                    if (record[field] != null && record[field] != '')
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: SelectableText('${record[field]}'),
                      ),
                  if (writable)
                    OutlinedButton.icon(
                      onPressed: busy ? null : editBase,
                      icon: const Icon(Icons.edit_outlined),
                      label: const Text('Kontakt bearbeiten'),
                    ),
                  for (final kind in ['persons', 'addresses']) ...[
                    const SizedBox(height: 24),
                    Wrap(
                      spacing: 12,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(
                          kind == 'persons' ? 'Ansprechpartner' : 'Anschriften',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        if (writable)
                          TextButton.icon(
                            onPressed: () => nested(kind),
                            icon: const Icon(Icons.add),
                            label: const Text('Hinzufügen'),
                          ),
                      ],
                    ),
                    for (final item in (record[kind] as List? ?? []).map(
                      businessMap,
                    ))
                      Card(
                        child: ListTile(
                          title: Text(
                            '${item['name'] ?? item['label'] ?? item['street'] ?? ''}',
                          ),
                          subtitle: Text(
                            kind == 'persons'
                                ? [
                                        item['role_label'],
                                        item['email'],
                                        item['phone'],
                                      ]
                                      .where((s) => s != null && s != '')
                                      .join(' · ')
                                : '${item['street']}\n${item['postal_code'] ?? ''} ${item['city']} · ${item['country']}',
                          ),
                          onTap: writable ? () => nested(kind, item) : null,
                          trailing: writable
                              ? IconButton(
                                  tooltip: 'Entfernen',
                                  onPressed: () => remove(kind, item),
                                  icon: const Icon(Icons.delete_outline),
                                )
                              : null,
                        ),
                      ),
                  ],
                  if (widget.session.can('privacy.manage')) ...[
                    const SizedBox(height: 24),
                    const Divider(),
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        OutlinedButton.icon(
                          onPressed: busy ? null : export,
                          icon: const Icon(Icons.download_outlined),
                          label: const Text('Datenschutz-Prüfexport'),
                        ),
                        if (widget.session.canWrite('privacy.manage'))
                          TextButton(
                            onPressed: busy ? null : erase,
                            child: const Text('Kontaktlöschung prüfen'),
                          ),
                      ],
                    ),
                  ],
                ],
              ],
            ),
    );
  }
}

import 'package:flutter/material.dart';

import 'api.dart';
import 'design.dart';

String customerChoiceLabel(Map<String, dynamic> customer) {
  final address = (customer['address'] as String? ?? '')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
  return '${customer['name']}${address.isEmpty ? '' : ' · $address'}';
}

class CustomersPage extends StatefulWidget {
  final OfficeApi api;
  final Future<void> Function(Map<String, dynamic>) onNewProject;
  const CustomersPage({
    super.key,
    required this.api,
    required this.onNewProject,
  });
  @override
  State<CustomersPage> createState() => _CustomersPageState();
}

class _CustomersPageState extends State<CustomersPage> {
  final search = TextEditingController();
  List<Map<String, dynamic>> customers = [];
  bool busy = false, includeArchived = false, projectOpen = false;
  String? error;

  @override
  void initState() {
    super.initState();
    refresh();
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> read() async {
    final result = await widget.api.call('/api/customers');
    if (mounted)
      setState(
        () =>
            customers = [for (final c in result) Map<String, dynamic>.from(c)],
      );
  }

  Future<void> refresh() => run(read);

  Future<void> edit([Map<String, dynamic>? customer]) async {
    final values = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => CustomerDialog(customer: customer),
    );
    if (!mounted || values == null) return;
    // Preserve entered data when saving fails; the user can reopen their input.
    await save(values, customer);
  }

  Future<void> save(
    Map<String, dynamic> values,
    Map<String, dynamic>? customer,
  ) async {
    if (busy) return;
    var pending = values;
    while (mounted) {
      Object? failure;
      var saved = false;
      setState(() {
        busy = true;
        error = null;
      });
      try {
        await widget.api.call(
          customer == null
              ? '/api/customers'
              : '/api/customers/${customer['id']}',
          pending,
        );
        saved = true;
        await read();
      } catch (e) {
        failure = e;
        if (saved && mounted) setState(() => error = e.toString());
      } finally {
        if (mounted) setState(() => busy = false);
      }
      if (!mounted || saved || failure == null) return;
      if (widget.api.token == null) {
        setState(() => error = failure.toString());
        return;
      }
      // Wait for user input without a running network/loading indicator.
      final retry = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (_) => CustomerDialog(
          customer: customer,
          initial: pending,
          error: failure.toString(),
        ),
      );
      if (!mounted || retry == null) return;
      pending = retry;
    }
  }

  Future<void> project(Map<String, dynamic> customer) async {
    if (busy || projectOpen) return;
    setState(() => projectOpen = true);
    try {
      await widget.onNewProject(customer);
      if (mounted && widget.api.token != null) await refresh();
    } finally {
      if (mounted) setState(() => projectOpen = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final query = search.text.trim().toLowerCase();
    final filtered = customers
        .where(
          (c) =>
              (includeArchived || c['active'] == 1) &&
              '${c['name']} ${c['contact']} ${c['email']} ${c['phone']} ${c['address']}'
                  .toLowerCase()
                  .contains(query),
        )
        .toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Kunden'),
        actions: [
          IconButton(
            tooltip: 'Aktualisieren',
            onPressed: busy ? null : refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
          const SizedBox(width: 16),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1160),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 12, 24, 40),
            children: [
              PageHeading(
                eyebrow: 'Kontakte & Zusammenarbeit',
                title: 'Ihre Kunden. Im Blick.',
                subtitle: 'Kontaktdaten und Ansprechpartner für Ihre Projekte.',
                action: FilledButton.icon(
                  onPressed: busy ? null : () => edit(),
                  icon: const Icon(Icons.person_add_alt_1_outlined, size: 18),
                  label: const Text('Kunde anlegen'),
                ),
              ),
              const SizedBox(height: 28),
              if (busy)
                const Padding(
                  padding: EdgeInsets.only(bottom: 20),
                  child: LinearProgressIndicator(minHeight: 2),
                ),
              if (error != null) Notice(error!),
              Wrap(
                spacing: 16,
                runSpacing: 12,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: MediaQuery.sizeOf(context).width < 600
                        ? double.infinity
                        : 340,
                    child: TextField(
                      controller: search,
                      onChanged: (_) => setState(() {}),
                      decoration: InputDecoration(
                        hintText: 'Kunden suchen',
                        prefixIcon: const Icon(Icons.search_rounded, size: 20),
                        suffixIcon: query.isEmpty
                            ? null
                            : IconButton(
                                tooltip: 'Suche zurücksetzen',
                                onPressed: () => setState(search.clear),
                                icon: const Icon(Icons.close_rounded, size: 17),
                              ),
                      ),
                    ),
                  ),
                  FilterChip(
                    label: const Text('Archivierte anzeigen'),
                    selected: includeArchived,
                    onSelected: (v) => setState(() => includeArchived = v),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              OfficeSurface(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          'Kundenübersicht',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(width: 10),
                        StatusPill('${filtered.length}'),
                      ],
                    ),
                    const SizedBox(height: 18),
                    const Divider(),
                    if (filtered.isEmpty && !busy)
                      EmptyState(
                        title: query.isEmpty
                            ? 'Noch keine passenden Kunden.'
                            : 'Kein passender Kunde.',
                        description: query.isEmpty
                            ? 'Legen Sie einen Kunden an oder zeigen Sie archivierte Kontakte an.'
                            : 'Suchen Sie nach Name, Ansprechpartner, E-Mail oder Ort.',
                        icon: Icons.contacts_outlined,
                      ),
                    for (final c in filtered)
                      Material(
                        color: Colors.transparent,
                        child: InkWell(
                          borderRadius: BorderRadius.circular(12),
                          onTap: busy ? null : () => edit(c),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              vertical: 20,
                              horizontal: 4,
                            ),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const IconTile(Icons.business_outlined),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        c['name'],
                                        style: const TextStyle(
                                          fontSize: 15,
                                          fontWeight: FontWeight.w600,
                                          letterSpacing: -.2,
                                        ),
                                      ),
                                      if ((c['contact'] as String).isNotEmpty)
                                        Padding(
                                          padding: const EdgeInsets.only(
                                            top: 4,
                                          ),
                                          child: Text(
                                            c['contact'],
                                            style: const TextStyle(
                                              fontSize: 12,
                                              color: OfficeColors.muted,
                                            ),
                                          ),
                                        ),
                                      if ((c['email'] as String).isNotEmpty ||
                                          (c['phone'] as String).isNotEmpty)
                                        Padding(
                                          padding: const EdgeInsets.only(
                                            top: 6,
                                          ),
                                          child: Text(
                                            [
                                              c['email'],
                                              c['phone'],
                                            ].where((s) => s != '').join(' · '),
                                            style: const TextStyle(
                                              fontSize: 12,
                                              color: OfficeColors.muted,
                                            ),
                                          ),
                                        ),
                                      if ((c['address'] as String).isNotEmpty)
                                        Padding(
                                          padding: const EdgeInsets.only(
                                            top: 4,
                                          ),
                                          child: Text(
                                            c['address'],
                                            maxLines: 2,
                                            overflow: TextOverflow.ellipsis,
                                            style: const TextStyle(
                                              fontSize: 11,
                                              color: OfficeColors.muted,
                                            ),
                                          ),
                                        ),
                                      const SizedBox(height: 10),
                                      Wrap(
                                        spacing: 8,
                                        runSpacing: 6,
                                        children: [
                                          StatusPill(
                                            c['active'] == 1
                                                ? 'Aktiv'
                                                : 'Archiviert',
                                            positive: c['active'] == 1,
                                          ),
                                          StatusPill(
                                            '${c['project_count']} ${c['project_count'] == 1 ? 'Projekt' : 'Projekte'}',
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                                if (c['active'] == 1)
                                  IconButton(
                                    tooltip:
                                        'Projekt für diesen Kunden anlegen',
                                    onPressed: busy || projectOpen
                                        ? null
                                        : () => project(c),
                                    icon: const Icon(
                                      Icons.create_new_folder_outlined,
                                      size: 20,
                                    ),
                                  ),
                                const Padding(
                                  padding: EdgeInsets.only(top: 14),
                                  child: Icon(
                                    Icons.chevron_right_rounded,
                                    size: 18,
                                    color: OfficeColors.muted,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class CustomerDialog extends StatefulWidget {
  final Map<String, dynamic>? customer, initial;
  final String? error;
  const CustomerDialog({super.key, this.customer, this.initial, this.error});
  @override
  State<CustomerDialog> createState() => _CustomerDialogState();
}

class CustomerAssignmentDialog extends StatefulWidget {
  final List<Map<String, dynamic>> customers;
  final String? customerId;
  const CustomerAssignmentDialog({
    super.key,
    required this.customers,
    this.customerId,
  });
  @override
  State<CustomerAssignmentDialog> createState() =>
      _CustomerAssignmentDialogState();
}

class _CustomerAssignmentDialogState extends State<CustomerAssignmentDialog> {
  final form = GlobalKey<FormState>();
  late String selected;
  @override
  void initState() {
    super.initState();
    selected = widget.customers.any((c) => c['id'] == widget.customerId)
        ? widget.customerId!
        : '';
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Projektkunde zuordnen'),
    content: SizedBox(
      width: 500,
      child: Form(
        key: form,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Die Zuordnung gilt für das Projekt und neue Berichte. Bestehende Berichte behalten ihre damaligen Kundendaten.',
              style: TextStyle(fontSize: 13, color: OfficeColors.muted),
            ),
            const SizedBox(height: 22),
            DropdownButtonFormField<String>(
              initialValue: selected,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Kunde'),
              items: [
                const DropdownMenuItem(
                  value: '',
                  child: Text('Bitte auswählen'),
                ),
                for (final c in widget.customers)
                  DropdownMenuItem(
                    value: c['id'] as String,
                    child: Text(
                      customerChoiceLabel(c),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: (v) => setState(() => selected = v!),
              validator: (v) => (v ?? '').isEmpty ? 'Kunden auswählen.' : null,
            ),
            if (widget.customers.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text(
                  'Bitte zuerst einen aktiven Kunden in der Kundenverwaltung anlegen.',
                ),
              ),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(
        onPressed: widget.customers.isEmpty
            ? null
            : () {
                if (form.currentState!.validate())
                  Navigator.pop(context, selected);
              },
        child: const Text('Zuordnen'),
      ),
    ],
  );
}

class _CustomerDialogState extends State<CustomerDialog> {
  final form = GlobalKey<FormState>();
  late final Map<String, TextEditingController> fields;
  late bool active;
  @override
  void initState() {
    super.initState();
    final values = widget.initial ?? widget.customer ?? {};
    fields = {
      for (final field in [
        'name',
        'contact',
        'email',
        'phone',
        'address',
        'notes',
      ])
        field: TextEditingController(text: values[field] as String? ?? ''),
    };
    active =
        widget.initial?['active'] as bool? ??
        (widget.customer == null || widget.customer!['active'] == 1);
  }

  @override
  void dispose() {
    for (final c in fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  void submit() {
    if (!form.currentState!.validate()) return;
    Navigator.pop(context, <String, dynamic>{
      for (final entry in fields.entries) entry.key: entry.value.text.trim(),
      'active': active,
    });
  }

  Widget field(
    String key,
    String label,
    int maximum, {
    int lines = 1,
    TextInputType? keyboard,
  }) => TextFormField(
    controller: fields[key],
    maxLength: maximum,
    minLines: lines,
    maxLines: lines > 1 ? lines + 3 : 1,
    keyboardType:
        keyboard ?? (lines > 1 ? TextInputType.multiline : TextInputType.text),
    textInputAction: lines > 1 ? TextInputAction.newline : TextInputAction.next,
    decoration: InputDecoration(
      labelText: label,
      alignLabelWithHint: lines > 1,
      counterText: key == 'notes' ? null : '',
    ),
    validator: (value) {
      if (key == 'name' && (value ?? '').trim().isEmpty)
        return 'Kundennamen eingeben.';
      if (key == 'email' &&
          (value ?? '').trim().isNotEmpty &&
          !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(value!.trim()))
        return 'Gültige E-Mail-Adresse eingeben.';
      return null;
    },
  );

  @override
  Widget build(BuildContext context) => AlertDialog(
    scrollable: true,
    title: Text(widget.customer == null ? 'Kunde anlegen' : 'Kunde bearbeiten'),
    content: SizedBox(
      width: 560,
      child: Form(
        key: form,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (widget.error != null) Notice(widget.error!),
            const Text(
              'Nur der Kundenname ist erforderlich.',
              style: TextStyle(fontSize: 12, color: OfficeColors.muted),
            ),
            const SizedBox(height: 20),
            field('name', 'Kundenname / Firma', 500),
            const SizedBox(height: 12),
            field('contact', 'Ansprechpartner', 200),
            const SizedBox(height: 12),
            field('email', 'E-Mail', 254, keyboard: TextInputType.emailAddress),
            const SizedBox(height: 12),
            field('phone', 'Telefon', 100, keyboard: TextInputType.phone),
            const SizedBox(height: 12),
            field('address', 'Adresse', 2000, lines: 2),
            const SizedBox(height: 12),
            field('notes', 'Interne Notizen', 5000, lines: 3),
            if (widget.customer != null) ...[
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text(
                  'Kunde aktiv',
                  style: TextStyle(fontSize: 14),
                ),
                subtitle: const Text(
                  'Archivierte Kunden bleiben in vorhandenen Projekten und Dokumenten erhalten.',
                  style: TextStyle(fontSize: 11),
                ),
                value: active,
                onChanged: (v) => setState(() => active = v),
              ),
            ],
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Abbrechen'),
      ),
      FilledButton(onPressed: submit, child: const Text('Speichern')),
    ],
  );
}

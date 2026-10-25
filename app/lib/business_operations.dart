import 'package:flutter/material.dart';

import 'api.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'business_documents.dart' show businessPositionKinds;
import 'business_documentation.dart';
import 'business_workflows.dart';
import 'design.dart';

typedef _Section = ({
  String id,
  String label,
  String module,
  String read,
  String write,
  bool scoped,
});
const _sections = <String, List<_Section>>{
  'contacts': [
    (
      id: 'contacts',
      label: 'Kontakte',
      module: 'foundation',
      read: 'contacts.read',
      write: 'contacts.write',
      scoped: false,
    ),
  ],
  'material': [
    (
      id: 'articles',
      label: 'Artikel und Leistungen',
      module: 'documents',
      read: 'finance.read',
      write: 'finance.write',
      scoped: false,
    ),
    (
      id: 'inventory/locations',
      label: 'Lagerorte',
      module: 'inventory',
      read: 'inventory.read',
      write: 'inventory.write',
      scoped: false,
    ),
    (
      id: 'inventory/stock',
      label: 'Bestände',
      module: 'inventory',
      read: 'inventory.read',
      write: '',
      scoped: false,
    ),
    (
      id: 'inventory/movements',
      label: 'Lagerbewegungen',
      module: 'inventory',
      read: 'inventory.read',
      write: 'inventory.write',
      scoped: false,
    ),
    (
      id: 'inventory/reservations',
      label: 'Reservierungen',
      module: 'inventory',
      read: 'inventory.read',
      write: 'inventory.write',
      scoped: true,
    ),
    (
      id: 'budgets',
      label: 'Projektbudget',
      module: 'inventory',
      read: 'finance.read',
      write: 'finance.write',
      scoped: true,
    ),
  ],
  'personnel': [
    (
      id: 'time/accounts',
      label: 'Zeitkonto und Freigabe',
      module: 'time',
      read: 'time.own',
      write: '',
      scoped: false,
    ),
    (
      id: 'employees',
      label: 'Mitarbeiter',
      module: 'planning',
      read: 'personnel.read',
      write: 'personnel.manage',
      scoped: false,
    ),
    (
      id: 'absences',
      label: 'Abwesenheiten',
      module: 'planning',
      read: 'time.own',
      write: 'time.own',
      scoped: false,
    ),
    (
      id: 'resources',
      label: 'Fahrzeuge und Werkzeuge',
      module: 'planning',
      read: 'planning.read',
      write: 'planning.write',
      scoped: false,
    ),
    (
      id: 'time/categories',
      label: 'Zeitkategorien',
      module: 'time',
      read: 'time.own',
      write: 'personnel.manage',
      scoped: false,
    ),
  ],
  'documentation': [
    (
      id: 'checklists',
      label: 'Technikerchecklisten',
      module: 'operations',
      read: 'documents.read',
      write: 'documents.write',
      scoped: true,
    ),
    (
      id: 'service-reports',
      label: 'Serviceberichte',
      module: 'operations',
      read: 'documents.read',
      write: 'documents.write',
      scoped: true,
    ),
    (
      id: 'diary',
      label: 'Bautagesberichte',
      module: 'operations',
      read: 'documents.read',
      write: 'documents.write',
      scoped: true,
    ),
    (
      id: 'defects',
      label: 'Mängel',
      module: 'operations',
      read: 'documents.read',
      write: 'documents.write',
      scoped: true,
    ),
    (
      id: 'measurements',
      label: 'Aufmaß',
      module: 'operations',
      read: 'documents.read',
      write: 'documents.write',
      scoped: true,
    ),
  ],
  'maintenance': [
    (
      id: 'assets',
      label: 'Anlagen',
      module: 'maintenance',
      read: 'documents.read',
      write: 'documents.write',
      scoped: true,
    ),
    (
      id: 'maintenance/contracts',
      label: 'Wartungsverträge',
      module: 'maintenance',
      read: 'documents.read',
      write: 'projects.manage',
      scoped: true,
    ),
    (
      id: 'maintenance/history',
      label: 'Wartungshistorie',
      module: 'maintenance',
      read: 'documents.read',
      write: '',
      scoped: true,
    ),
  ],
  'settings': [
    (
      id: 'project-statuses',
      label: 'Projektstatus',
      module: 'foundation',
      read: 'documents.read',
      write: 'settings.manage',
      scoped: false,
    ),
  ],
};

class BusinessAreaPage extends StatefulWidget {
  const BusinessAreaPage({
    super.key,
    required this.session,
    required this.area,
  });
  final BusinessSession session;
  final String area;
  @override
  State<BusinessAreaPage> createState() => _BusinessAreaPageState();
}

class _BusinessAreaPageState extends State<BusinessAreaPage> {
  String? selected, error;
  bool loading = false;
  int epoch = 0, refreshSerial = 0;
  final references = <String, Map<String, String>>{};
  List<Map<String, dynamic>> movements = [];
  List<_Section> get sections => (_sections[widget.area] ?? [])
      .where(
        (s) => widget.session.hasModule(s.module) && widget.session.can(s.read),
      )
      .toList();
  @override
  void initState() {
    super.initState();
    widget.session.addListener(changed);
    if (sections.isNotEmpty) {
      selected = sections.first.id;
      loadReferences();
    }
  }

  void changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    epoch++;
    widget.session.removeListener(changed);
    super.dispose();
  }

  Future<void> loadReferences() async {
    final current = ++epoch;
    setState(() {
      loading = true;
      error = null;
      references.clear();
      movements = [];
    });
    final section = sections
        .where((section) => section.id == selected)
        .firstOrNull;
    if (section?.scoped == true && widget.session.projectId == null) {
      setState(() => loading = false);
      return;
    }
    final paths = switch (selected) {
      'inventory/movements' ||
      'inventory/reservations' => ['inventory/locations'],
      'maintenance/contracts' => ['assets'],
      'absences' => ['employees'],
      'employees' => ['users'],
      _ => <String>[],
    };
    try {
      if ([
        'inventory/movements',
        'inventory/reservations',
      ].contains(selected)) {
        final articles = await inventoryArticles();
        if (!mounted || current != epoch || !widget.session.allowed) return;
        references['articles'] = {
          for (final item in articles) '${item['id']}': '${item['name']}',
        };
      }
      for (final path in paths) {
        final response = path == 'users'
            ? await widget.session.api.call('/api/users')
            : await widget.session.read(widget.session.query('/$path'));
        if (!mounted || current != epoch || !widget.session.allowed) return;
        final items = path == 'users'
            ? (response as List).map(businessMap).toList()
            : businessItems(response);
        references[path] = {
          for (final r in items)
            '${r['id']}': '${r['name'] ?? r['email'] ?? r['title'] ?? r['id']}',
        };
      }
      if (selected == 'inventory/movements') {
        final rows = businessItems(
          await widget.session.read(
            widget.session.query('/inventory/movements'),
          ),
        );
        if (!mounted || current != epoch || !widget.session.allowed) return;
        movements = rows;
      }
    } catch (e) {
      if (mounted && current == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && current == epoch) setState(() => loading = false);
    }
  }

  Future<List<Map<String, dynamic>>> inventoryArticles() async {
    if (!widget.session.hasFeature('inventory_article_refs')) {
      // This request has no project query: a project-only financial grant is
      // insufficient to read the legacy global catalog with its prices.
      final meta = businessMap(await widget.session.read('/capabilities'));
      final global = meta['global_permissions'] ?? meta['permissions'];
      if (global is! List || !global.contains('finance.read')) {
        throw const ApiException(
          409,
          'Für die sichere Artikelauswahl ist ein Serverupdate erforderlich. Finanzrechte werden dafür nicht erweitert.',
        );
      }
      return businessItems(await widget.session.read('/articles'))
          .where(
            (row) =>
                row['active'] != false &&
                ['material', 'machine'].contains(row['kind']),
          )
          .toList();
    }
    final items = <Map<String, dynamic>>[];
    String? after;
    final seen = <String>{};
    for (var page = 0; page < 50; page++) {
      final result = businessMap(
        await widget.session.read(
          widget.session.query('/inventory/articles', {
            'limit': '200',
            if (after != null) 'after': after,
          }),
        ),
      );
      items.addAll(businessItems(result));
      if (result['has_more'] == false) return items;
      final next = result['next_after'];
      if (result['has_more'] != true ||
          next is! String ||
          !RegExp(r'^[a-f0-9]{32}$').hasMatch(next) ||
          !seen.add(next)) {
        throw const ApiException(
          502,
          'Die Artikelauswahl wurde unvollständig geliefert. Bitte erneut laden.',
        );
      }
      after = next;
    }
    throw const ApiException(
      413,
      'Mehr als 10.000 Artikel passen nicht in diese Auswahl. Bitte den aktiven Artikelbestand begrenzen.',
    );
  }

  List<BusinessField> fields(String id) => switch (id) {
    'service-reports' => const [
      BusinessField('title', 'Titel', required: true),
      BusinessField(
        'description',
        'Durchgeführte Arbeiten',
        type: BusinessInput.multiline,
      ),
      BusinessField('notes', 'Notizen', type: BusinessInput.multiline),
    ],
    'contacts' => const [
      BusinessField('name', 'Name / Firma', required: true),
      BusinessField(
        'entity_type',
        'Kontaktart',
        type: BusinessInput.choice,
        initial: 'company',
        required: true,
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
      BusinessField('contact', 'Ansprechpartner'),
      BusinessField('email', 'E-Mail'),
      BusinessField('phone', 'Telefon'),
      BusinessField('address', 'Anschrift', type: BusinessInput.multiline),
      BusinessField('notes', 'Notizen', type: BusinessInput.multiline),
      BusinessField(
        'active',
        'Aktiv',
        type: BusinessInput.toggle,
        initial: true,
      ),
    ],
    'articles' => const [
      BusinessField('code', 'Artikelnummer / Barcode'),
      BusinessField('name', 'Bezeichnung', required: true),
      BusinessField(
        'kind',
        'Art',
        type: BusinessInput.choice,
        required: true,
        initial: 'material',
        choices: businessPositionKinds,
      ),
      BusinessField('unit', 'Einheit', required: true, initial: 'C62'),
      BusinessField(
        'unit_price_net',
        'Verkaufspreis netto (€)',
        type: BusinessInput.decimal,
        required: true,
        initial: '0',
      ),
      BusinessField(
        'cost_price_net',
        'Einkaufspreis netto (€)',
        type: BusinessInput.decimal,
        required: true,
        initial: '0',
      ),
      BusinessField(
        'tax_rate',
        'Umsatzsteuer (%)',
        type: BusinessInput.decimal,
        required: true,
        initial: '19',
      ),
      BusinessField(
        'active',
        'Aktiv',
        type: BusinessInput.toggle,
        initial: true,
      ),
    ],
    'inventory/locations' => const [
      BusinessField('name', 'Lagerort', required: true),
      BusinessField(
        'active',
        'Aktiv',
        type: BusinessInput.toggle,
        initial: true,
      ),
    ],
    'inventory/movements' => [
      const BusinessField(
        'kind',
        'Bewegung',
        type: BusinessInput.choice,
        required: true,
        initial: 'receive',
        choices: {
          'receive': 'Zugang',
          'issue': 'Projektentnahme',
          'return': 'Rückgabe',
          'transfer': 'Umlagerung',
        },
      ),
      BusinessField(
        'article_id',
        'Artikel',
        type: BusinessInput.choice,
        choices: references['articles'] ?? {},
      ),
      BusinessField(
        'reversal_of',
        'Ursprüngliche Projektentnahme',
        type: BusinessInput.choice,
        hint: 'Für Rückgaben auswählen. Artikel und Projekt werden aus dieser Entnahme übernommen.',
        choices: {
          for (final row in movements.where(
            (row) =>
                row['kind'] == 'issue' &&
                row['project_id'] != null &&
                (widget.session.projectId == null ||
                    row['project_id'] == widget.session.projectId),
          ))
            '${row['id']}':
                '${row['article_snapshot']?['name'] ?? references['articles']?['${row['article_id']}'] ?? 'Material'} · ${row['quantity']} ${row['article_snapshot']?['unit'] ?? ''} · ${businessDate(row['created_at'], time: true)}',
        },
      ),
      BusinessField(
        'from_location_id',
        'Aus Lagerort',
        type: BusinessInput.choice,
        choices: references['inventory/locations'] ?? {},
      ),
      BusinessField(
        'to_location_id',
        'In Lagerort',
        type: BusinessInput.choice,
        choices: references['inventory/locations'] ?? {},
      ),
      if (widget.session.projectId == null)
        BusinessField(
          'project_id',
          'Projekt (für Entnahme/Rückgabe)',
          type: BusinessInput.choice,
          choices: {
            for (final p in widget.session.projects)
              '${p['id']}': '${p['name']}',
          },
        ),
      const BusinessField(
        'quantity',
        'Menge',
        type: BusinessInput.decimal,
        required: true,
      ),
      if (widget.session.can('finance.read'))
        const BusinessField(
          'unit_cost_net',
          'Einstandspreis netto je Einheit (€; optional)',
          type: BusinessInput.decimal,
          omitIfEmpty: true,
        ),
      const BusinessField(
        'note',
        'Buchungsnotiz',
        type: BusinessInput.multiline,
      ),
    ],
    'inventory/reservations' => [
      BusinessField(
        'article_id',
        'Artikel',
        type: BusinessInput.choice,
        required: true,
        choices: references['articles'] ?? {},
      ),
      BusinessField(
        'location_id',
        'Lagerort',
        type: BusinessInput.choice,
        required: true,
        choices: references['inventory/locations'] ?? {},
      ),
      const BusinessField(
        'quantity',
        'Menge',
        type: BusinessInput.decimal,
        required: true,
      ),
    ],
    'budgets' => const [
      BusinessField(
        'material_net',
        'Materialbudget netto (€)',
        type: BusinessInput.decimal,
        required: true,
        initial: '0',
      ),
      BusinessField(
        'labor_net',
        'Lohnbudget netto (€)',
        type: BusinessInput.decimal,
        required: true,
        initial: '0',
      ),
      BusinessField(
        'machine_net',
        'Maschinenbudget netto (€)',
        type: BusinessInput.decimal,
        required: true,
        initial: '0',
      ),
      BusinessField(
        'other_net',
        'Sonstiges Budget netto (€)',
        type: BusinessInput.decimal,
        required: true,
        initial: '0',
      ),
    ],
    'employees' => [
      BusinessField(
        'user_id',
        'Benutzerkonto',
        type: BusinessInput.choice,
        required: true,
        choices: references['users'] ?? {},
      ),
      const BusinessField('name', 'Name', required: true),
      const BusinessField(
        'weekly_minutes',
        'Sollzeit pro Woche (Minuten)',
        type: BusinessInput.integer,
        required: true,
        initial: 2400,
      ),
      const BusinessField(
        'hourly_cost_minor',
        'Interner Stundensatz (Cent)',
        type: BusinessInput.integer,
        required: true,
        initial: 0,
      ),
      const BusinessField(
        'employment_from',
        'Beschäftigt seit',
        type: BusinessInput.date,
      ),
      const BusinessField(
        'employment_to',
        'Beschäftigt bis',
        type: BusinessInput.date,
      ),
      const BusinessField(
        'active',
        'Aktiv',
        type: BusinessInput.toggle,
        initial: true,
      ),
    ],
    'resources' => const [
      BusinessField('name', 'Bezeichnung', required: true),
      BusinessField(
        'kind',
        'Art',
        type: BusinessInput.choice,
        required: true,
        initial: 'tool',
        choices: {
          'vehicle': 'Fahrzeug',
          'machine': 'Maschine',
          'tool': 'Werkzeug',
        },
      ),
      BusinessField('code', 'Inventarcode'),
      BusinessField(
        'active',
        'Aktiv',
        type: BusinessInput.toggle,
        initial: true,
      ),
    ],
    'absences' => [
      BusinessField(
        'employee_id',
        'Mitarbeiter',
        type: BusinessInput.choice,
        required: true,
        choices: references['employees'] ?? {},
      ),
      const BusinessField(
        'kind',
        'Art',
        type: BusinessInput.choice,
        required: true,
        initial: 'vacation',
        choices: {
          'vacation': 'Urlaub',
          'sick': 'Krankheit',
          'other': 'Sonstiges',
        },
      ),
      const BusinessField(
        'start_date',
        'Von',
        type: BusinessInput.date,
        required: true,
      ),
      const BusinessField(
        'end_date',
        'Bis',
        type: BusinessInput.date,
        required: true,
      ),
      const BusinessField('details', 'Hinweis', type: BusinessInput.multiline),
    ],
    'time/categories' => const [
      BusinessField('name', 'Kategorie', required: true),
      BusinessField(
        'supplement_percent',
        'Zuschlag (%)',
        type: BusinessInput.decimal,
        required: true,
        initial: '0',
      ),
      BusinessField(
        'active',
        'Aktiv',
        type: BusinessInput.toggle,
        initial: true,
      ),
    ],
    'diary' => const [
      BusinessField('title', 'Titel', required: true),
      BusinessField(
        'entry_date',
        'Datum',
        type: BusinessInput.date,
        required: true,
      ),
      BusinessField(
        'work',
        'Ausgeführte Arbeiten',
        type: BusinessInput.multiline,
      ),
      BusinessField(
        'issues',
        'Probleme und Besonderheiten',
        type: BusinessInput.multiline,
      ),
      BusinessField('weather', 'Wetter'),
      BusinessField(
        'crew_count',
        'Personenzahl',
        type: BusinessInput.integer,
        initial: 0,
      ),
      BusinessField('notes', 'Notizen', type: BusinessInput.multiline),
    ],
    'defects' => const [
      BusinessField('title', 'Mangel', required: true),
      BusinessField('details', 'Beschreibung', type: BusinessInput.multiline),
      BusinessField('location', 'Ort / Bereich'),
      BusinessField('due_date', 'Frist', type: BusinessInput.date),
      BusinessField(
        'status',
        'Status',
        type: BusinessInput.choice,
        required: true,
        initial: 'open',
        choices: {
          'open': 'Offen',
          'in_progress': 'In Bearbeitung',
          'resolved': 'Behoben',
          'accepted': 'Abgenommen',
        },
      ),
      BusinessField(
        'resolution',
        'Nachweis der Behebung / Abnahme',
        type: BusinessInput.multiline,
      ),
    ],
    'assets' => const [
      BusinessField('name', 'Anlage', required: true),
      BusinessField('asset_type', 'Anlagentyp'),
      BusinessField('serial_number', 'Seriennummer'),
      BusinessField('location', 'Standort'),
      BusinessField('notes', 'Notizen', type: BusinessInput.multiline),
      BusinessField(
        'active',
        'Aktiv',
        type: BusinessInput.toggle,
        initial: true,
      ),
    ],
    'maintenance/contracts' => [
      BusinessField(
        'asset_id',
        'Anlage',
        type: BusinessInput.choice,
        required: true,
        choices: references['assets'] ?? {},
      ),
      const BusinessField('title', 'Wartungsvertrag', required: true),
      const BusinessField(
        'anchor_date',
        'Erste Fälligkeit',
        type: BusinessInput.date,
        required: true,
      ),
      const BusinessField(
        'interval_unit',
        'Intervall',
        type: BusinessInput.choice,
        required: true,
        initial: 'months',
        choices: {'days': 'Tage', 'months': 'Kalendermonate'},
      ),
      const BusinessField(
        'interval_count',
        'Abstand',
        type: BusinessInput.integer,
        required: true,
        initial: 12,
      ),
      const BusinessField(
        'notes',
        'Vertragsnotizen',
        type: BusinessInput.multiline,
      ),
      const BusinessField(
        'active',
        'Aktiv',
        type: BusinessInput.toggle,
        initial: true,
      ),
    ],
    'project-statuses' => const [
      BusinessField('name', 'Statusname', required: true),
      BusinessField(
        'color',
        'Farbe',
        initial: '#64748B',
        required: true,
        hint: '#64748B',
      ),
      BusinessField(
        'position',
        'Reihenfolge',
        type: BusinessInput.integer,
        required: true,
        initial: 0,
      ),
      BusinessField(
        'terminal',
        'Abgeschlossener Zustand',
        type: BusinessInput.toggle,
        initial: false,
      ),
      BusinessField(
        'active',
        'Aktiv',
        type: BusinessInput.toggle,
        initial: true,
      ),
    ],
    _ => const [],
  };

  Map<String, dynamic> movementValues(Map<String, dynamic> values) {
    final kind = values['kind'];
    if (!['receive', 'issue', 'return', 'transfer'].contains(kind)) {
      throw const FormatException('Bitte eine Lagerbewegung auswählen.');
    }
    final result = <String, dynamic>{
      'kind': kind,
      'quantity': values['quantity'],
      'note': values['note'] ?? '',
    };
    final projectId = widget.session.projectId ?? values['project_id'];
    if (kind == 'return') {
      final source = movements
          .where(
            (row) =>
                row['id'] == values['reversal_of'] && row['kind'] == 'issue',
          )
          .firstOrNull;
      if (source == null ||
          source['project_id'] == null ||
          (projectId != null && projectId != source['project_id'])) {
        throw const FormatException(
          'Bitte die ursprüngliche Entnahme dieses Projekts auswählen.',
        );
      }
      result.addAll({
        'reversal_of': source['id'],
        'article_id': source['article_id'],
        'project_id': source['project_id'],
      });
    } else {
      final id = values['article_id'];
      if (id is! String || !references['articles']!.containsKey(id)) {
        throw const FormatException('Bitte einen Artikel auswählen.');
      }
      result['article_id'] = id;
      if (kind != 'transfer' && projectId != null)
        result['project_id'] = projectId;
      if (kind == 'receive' && values['unit_cost_net'] != null)
        result['unit_cost_net'] = values['unit_cost_net'];
    }
    if (kind == 'issue' || kind == 'transfer') {
      final location = values['from_location_id'];
      if (location is! String ||
          !references['inventory/locations']!.containsKey(location)) {
        throw const FormatException('Bitte den Quelllagerort auswählen.');
      }
      result['from_location_id'] = location;
    }
    if (kind != 'issue') {
      final location = values['to_location_id'];
      if (location is! String ||
          !references['inventory/locations']!.containsKey(location)) {
        throw const FormatException('Bitte den Ziellagerort auswählen.');
      }
      result['to_location_id'] = location;
    }
    if (kind == 'issue' && projectId == null)
      throw const FormatException(
        'Bitte ein Projekt für die Entnahme auswählen.',
      );
    if (kind == 'transfer' &&
        result['from_location_id'] == result['to_location_id']) {
      throw const FormatException(
        'Quell- und Ziellagerort müssen verschieden sein.',
      );
    }
    return result;
  }

  Future<void> movement() async {
    if (!widget.session.canWrite('inventory.write') || error != null) return;
    final key = 'movement-${DateTime.now().microsecondsSinceEpoch}';
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        title: 'Materialbewegung',
        readPermission: 'inventory.read',
        writePermission: 'inventory.write',
        fields: fields('inventory/movements'),
        onSave: (values) async {
          await widget.session.command(
            key,
            '/inventory/movements',
            movementValues(values),
          );
        },
      ),
    );
  }

  Future<void> schedule() async {
    await showDialog<bool>(
      context: context,
      builder: (_) => BusinessEditor(
        session: widget.session,
        readPermission: 'documents.read',
        writePermission: 'projects.manage',
        title: 'Fällige Wartungen planen',
        fields: const [
          BusinessField(
            'as_of',
            'Fälligkeiten bis',
            type: BusinessInput.date,
            required: true,
          ),
        ],
        initial: {'as_of': DateTime.now().toIso8601String().substring(0, 10)},
        onSave: (values) async {
          await widget.session.command(
            'maintenance-schedule-${values['as_of']}',
            '/maintenance/schedule',
            {'project_id': widget.session.projectId, ...values},
          );
        },
      ),
    );
    if (mounted) setState(() => refreshSerial++);
  }

  Future<void> workflow(String id, Map<String, dynamic> record) async {
    if (id == 'inventory/reservations') {
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: widget.session,
          readPermission: 'inventory.read',
          writePermission: 'inventory.write',
          title: 'Reserviertes Material entnehmen',
          fields: const [
            BusinessField(
              'quantity',
              'Entnahmemenge',
              type: BusinessInput.decimal,
              required: true,
            ),
          ],
          initial: {'quantity': record['remaining_quantity']},
          onSave: (values) async {
            await widget.session.command(
              'pick-${record['id']}-${record['revision']}',
              '/inventory/pick',
              {
                'project_id': widget.session.projectId,
                'items': [
                  {
                    'reservation_id': record['id'],
                    'quantity': values['quantity'],
                  },
                ],
              },
            );
          },
        ),
      );
    } else if (id == 'maintenance/history') {
      if (record['status'] != 'planned') {
        if (record['report_id'] != null)
          await Navigator.push<void>(
            context,
            MaterialPageRoute(
              builder: (_) => BusinessOperationDocumentPage(
                session: widget.session,
                path: '/service-reports',
                id: record['report_id'],
              ),
            ),
          );
        return;
      }
      final reports = businessItems(
        await widget.session.read(widget.session.query('/service-reports')),
      ).where((r) => r['status'] == 'signed').toList();
      if (!mounted || !widget.session.allowed) return;
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: widget.session,
          readPermission: 'documents.read',
          writePermission: 'documents.write',
          title: 'Wartung abschließen',
          fields: [
            BusinessField(
              'report_id',
              'Unterzeichneter Servicebericht',
              type: BusinessInput.choice,
              required: true,
              choices: {
                for (final r in reports)
                  '${r['id']}':
                      '${r['title']} · ${businessDate(r['signed_at'])}',
              },
            ),
          ],
          onSave: (values) async {
            await widget.session.command(
              'maintenance-complete-${record['id']}',
              '/maintenance/visits/${record['id']}/complete',
              {'revision': record['revision'], ...values},
            );
          },
        ),
      );
    } else if (id == 'absences') {
      await showDialog<bool>(
        context: context,
        builder: (_) => BusinessEditor(
          session: widget.session,
          readPermission: 'time.own',
          writePermission: 'time.approve',
          title: 'Abwesenheit entscheiden',
          fields: const [
            BusinessField(
              'status',
              'Entscheidung',
              type: BusinessInput.choice,
              required: true,
              initial: 'approved',
              choices: {
                'approved': 'Genehmigen',
                'rejected': 'Ablehnen',
                'cancelled': 'Genehmigte Abwesenheit zurücknehmen',
              },
            ),
          ],
          onSave: (values) async {
            await widget.session.command(
              'absence-approve-${record['id']}-${record['revision']}',
              '/absences/${record['id']}/approve',
              {'revision': record['revision'], ...values},
            );
          },
        ),
      );
    }
    if (mounted) setState(() => refreshSerial++);
  }

  @override
  Widget build(BuildContext context) {
    final available = sections;
    if (available.isEmpty)
      return const BusinessEmpty(
        'Kein freigegebener Bereich',
        'Die verfügbaren Funktionen richten sich nach Ihren Berechtigungen.',
      );
    final section =
        available.where((s) => s.id == selected).firstOrNull ?? available.first;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 0),
          child: DropdownButtonFormField<String>(
            initialValue: section.id,
            decoration: const InputDecoration(labelText: 'Bereich'),
            isExpanded: true,
            items: [
              for (final s in available)
                DropdownMenuItem(value: s.id, child: Text(s.label)),
            ],
            onChanged: (value) {
              setState(() => selected = value);
              loadReferences();
            },
          ),
        ),
        if (error != null)
          Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Notice(error!, error: true),
                TextButton.icon(
                  onPressed: loading ? null : loadReferences,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Auswahl erneut laden'),
                ),
              ],
            ),
          ),
        if (loading) const LinearProgressIndicator(),
        if (!loading)
          Expanded(
            child: section.scoped && widget.session.projectId == null
                ? const BusinessEmpty(
                    'Projekt auswählen',
                    'Öffnen Sie diesen Bereich in der passenden Projektmappe. So bleibt die Zuordnung eindeutig.',
                  )
                : section.id == 'time/accounts'
                ? BusinessTimeAccountsPage(session: widget.session)
                : section.id == 'checklists'
                ? BusinessChecklistsPage(session: widget.session)
                : BusinessCollection(
                    key: ValueKey(
                      '${widget.area}/${section.id}/$refreshSerial',
                    ),
                    session: widget.session,
                    path: '/${section.id}',
                    title: section.label,
                    readPermission: section.read,
                    writePermission: error == null ? section.write : '',
                    fields: fields(section.id),
                    onCreate: section.id == 'inventory/movements'
                        ? movement
                        : section.id == 'measurements'
                        ? () async {
                            await Navigator.push<void>(
                              context,
                              MaterialPageRoute(
                                builder: (_) => BusinessMeasurementEditor(
                                  session: widget.session,
                                ),
                              ),
                            );
                          }
                        : null,
                    onOpen:
                        [
                          'measurements',
                          'diary',
                          'service-reports',
                        ].contains(section.id)
                        ? (record) async {
                            await Navigator.push<void>(
                              context,
                              MaterialPageRoute(
                                builder: (_) => BusinessOperationDocumentPage(
                                  session: widget.session,
                                  path: '/${section.id}',
                                  id: record['id'],
                                  fields: fields(section.id),
                                ),
                              ),
                            );
                          }
                        : (section.id == 'inventory/reservations' &&
                                  widget.session.canWrite('inventory.write')) ||
                              (section.id == 'maintenance/history' &&
                                  widget.session.canWrite('documents.write')) ||
                              (section.id == 'absences' &&
                                  widget.session.canWrite('time.approve'))
                        ? (record) => workflow(section.id, record)
                        : null,
                    actions:
                        [
                              'maintenance/contracts',
                              'maintenance/history',
                            ].contains(section.id) &&
                            widget.session.canWrite('projects.manage')
                        ? OutlinedButton.icon(
                            onPressed: schedule,
                            icon: const Icon(Icons.event_repeat),
                            label: const Text('Fällige Wartungen planen'),
                          )
                        : null,
                    projectScoped:
                        section.scoped || section.id == 'inventory/movements',
                    editable: ![
                      'inventory/movements',
                      'inventory/reservations',
                      'inventory/stock',
                      'maintenance/history',
                    ].contains(section.id),
                    updateAtCollection: section.id == 'budgets',
                    fixed: {if (section.id == 'articles') 'currency': 'EUR'},
                    titleOf: (r) =>
                        '${r['name'] ?? r['title'] ?? r['article_name'] ?? r['article_snapshot']?['name'] ?? r['article_id'] ?? section.label}',
                    subtitleOf: (r) => section.id == 'inventory/stock'
                        ? 'Bestand: ${r['on_hand']} · Reserviert: ${r['reserved']} · Verfügbar: ${r['available']}'
                        : section.id == 'inventory/movements'
                        ? '${r['quantity']} · ${r['kind']} · ${businessDate(r['created_at'], time: true)}'
                        : section.id == 'maintenance/history'
                        ? 'Fällig: ${businessDate(r['due_date'])} · ${r['status']}'
                        : '${r['notes'] ?? r['status'] ?? r['email'] ?? ''}',
                  ),
          ),
      ],
    );
  }
}

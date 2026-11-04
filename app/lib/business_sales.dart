import 'package:flutter/material.dart';

import 'api.dart';
import 'business_documents.dart';
import 'business_catalog_prices.dart';
import 'business_session.dart';
import 'business_widgets.dart';
import 'design.dart';

const salesStages = {
  'new': 'Neu',
  'qualified': 'Qualifiziert',
  'proposal': 'Angebot',
  'negotiation': 'Verhandlung',
  'won': 'Gewonnen',
  'lost': 'Verloren',
};
int salesMinor(Object? value) {
  final match = RegExp(r'^(\d{1,10})(?:[.,](\d{1,2}))?$')
      .firstMatch('$value'.trim());
  if (match == null)
    throw const FormatException(
      'Netto-Erwartungswert mit höchstens zwei Nachkommastellen angeben.',
    );
  final result =
      int.parse(match[1]!) * 100 + int.parse((match[2] ?? '').padRight(2, '0'));
  if (result > 1000000000000)
    throw const FormatException('Erwartungswert ist zu groß.');
  return result;
}

Map<String, dynamic> salesValues(
  Map<String, dynamic> values, {
  required String customerId,
  String? inquiryId,
  Map<String, dynamic>? previous,
}) {
  final probability = values['probability_percent'];
  if (probability is! int ||
      probability < 0 ||
      probability > 100 ||
      !salesStages.containsKey(values['stage']))
    throw const FormatException('Phase und Wahrscheinlichkeit prüfen.');
  if (values['stage'] == 'won' && probability != 100 ||
      values['stage'] == 'lost' && probability != 0)
    throw const FormatException('Gewonnen benötigt 100 %, verloren 0 %.');
  if (['won', 'lost'].contains(values['stage']) &&
      '${values['closure_reason'] ?? ''}'.trim().isEmpty)
    throw const FormatException('Abschlussentscheidung begründen.');
  return {
    if (previous != null) 'id': previous['id'],
    'revision': previous?['revision'] ?? 0,
    'customer_id': customerId,
    'inquiry_id': inquiryId,
    'title': values['title'],
    'person_id': values['person_id'] == '' ? null : values['person_id'],
    'stage': values['stage'],
    'expected_net_minor': salesMinor(values['expected_net']),
    'probability_percent': probability,
    'responsible_id': values['responsible_id'],
    'follow_up_on': values['follow_up_on'] == ''
        ? null
        : values['follow_up_on'],
    'expected_close_on': values['expected_close_on'] == ''
        ? null
        : values['expected_close_on'],
    'description': values['description'] ?? '',
    'closure_reason': values['closure_reason'] ?? '',
  };
}

String _money(Object? value) => value is int
    ? '${(value / 100).toStringAsFixed(2).replaceAll('.', ',')} €'
    : 'Nicht bestätigt';

class BusinessSalesPage extends StatefulWidget {
  const BusinessSalesPage({
    super.key,
    required this.session,
    this.customerId,
    this.onProject,
  });
  final BusinessSession session;
  final String? customerId;
  final void Function(Map<String, dynamic>)? onProject;
  @override
  State<BusinessSalesPage> createState() => _BusinessSalesPageState();
}

class _BusinessSalesPageState extends State<BusinessSalesPage> {
  BusinessSession get session => widget.session;
  bool get allowed =>
      session.hasFeature('sales_pipeline') &&
      session.hasModule('sales') &&
      session.can('contacts.read');
  bool get writable => allowed && session.canWrite('contacts.write');
  Map<String, dynamic>? listing, selected;
  List<Map<String, dynamic>> activities = [];
  String? selectedId, error, stage;
  final query = TextEditingController();
  int epoch = 0;
  CatalogPriceFlow? catalogFlow;
  bool loading = false;
  @override
  void initState() {
    super.initState();
    session.addListener(changed);
    load();
  }

  @override
  void dispose() {
    catalogFlow?.dispose();
    epoch++;
    session.removeListener(changed);
    query.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant BusinessSalesPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != session ||
        oldWidget.customerId != widget.customerId) {
      catalogFlow?.dispose();
      oldWidget.session.removeListener(changed);
      session.addListener(changed);
      epoch++;
      listing = null;
      selected = null;
      selectedId = null;
      activities = [];
      error = null;
      load();
    }
  }

  void changed() {
    if (!mounted) return;
    if (!allowed) {
      epoch++;
      listing = null;
      selected = null;
      activities = [];
    }
    setState(() {});
  }

  void check([bool write = false]) {
    if (!allowed || write && !writable)
      throw const ApiException(
        403,
        'Die aktuelle Freigabe für Verkaufschancen fehlt.',
      );
  }

  Future<void> load() async {
    final version = ++epoch;
    setState(() {
      loading = true;
      error = null;
    });
    try {
      check();
      if (selectedId != null) {
        final value = businessMap(
          await session.read('/sales/opportunities/$selectedId'),
        );
        final events = businessItems(
          await session.read('/sales/opportunities/$selectedId/activities'),
        );
        check();
        if (mounted && version == epoch)
          setState(() {
            selected = value;
            activities = events;
          });
      } else {
        final parameters = {
          'q': query.text,
          if (stage != null) 'stage': stage!,
          if (widget.customerId != null) 'customer_id': widget.customerId!,
        };
        final value = businessMap(
          await session.read(
            '/sales/opportunities?${Uri(queryParameters: parameters).query}',
          ),
        );
        check();
        if (mounted && version == epoch) setState(() => listing = value);
      }
    } catch (e) {
      if (mounted && version == epoch) setState(() => error = '$e');
    } finally {
      if (mounted && version == epoch) setState(() => loading = false);
    }
  }

  Future<void> attempt(Future<void> Function() operation) async {
    try {
      await operation();
    } catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<Map<String, dynamic>> write(
    String key,
    String path,
    Map<String, dynamic> body,
  ) async {
    check(true);
    final owner = session;
    await owner.load();
    if (!mounted || !identical(owner, session))
      throw const ApiException(0, 'Verkaufskontext gewechselt.');
    check(true);
    final result = owner.pending(key)
        ? await session.repeatSalesCommand(key)
        : await session.command(
            key,
            path,
            body,
            validateResult: (raw) {
              final value = businessMap(raw);
              final identifier = value['id'] ?? value['project_id'];
              if (identifier is! String ||
                  !RegExp(r'^[a-f0-9]{32}$').hasMatch(identifier))
                throw const ApiException(
                  0,
                  'Der ursprüngliche Vorgang wurde nicht eindeutig bestätigt.',
                );
              if (path == '/sales/opportunities' &&
                  (value['customer_id'] != body['customer_id'] ||
                      value['revision'] != body['revision'] + 1 ||
                      body['id'] != null && value['id'] != body['id']))
                throw const ApiException(
                  0,
                  'Die Bestätigung passt nicht zur ursprünglichen Verkaufschance.',
                );
            },
          );
    check(true);
    return businessMap(result);
  }

  Future<void> editor(
    String title,
    String key,
    List<BusinessField> fields,
    Future<void> Function(Map<String, dynamic>) save, {
    Map<String, dynamic> initial = const {},
  }) async {
    check(true);
    if (!mounted) return;
    final builder = (BuildContext _) => BusinessEditor(
      session: session,
      title: title,
      fields: fields,
      initial: initial,
      readPermission: 'contacts.read',
      writePermission: 'contacts.write',
      readAllowed: () => allowed,
      pendingKey: key,
      saveLabel: session.pending(key)
          ? 'Ursprünglichen Vorgang prüfen'
          : 'Speichern',
      onSave: save,
    );
    if (catalogFlow != null) {
      await catalogFlow!.dialog<bool>(builder);
    } else {
      await showDialog<bool>(context: context, builder: builder);
    }
  }

  Future<void> choose() async {
    check(true);
    final options = businessMap(await session.read('/sales/options'));
    check(true);
    final customers = businessItems(options['customers']);
    if (customers.isEmpty)
      throw const FormatException(
        'Zuerst einen Kunden oder Interessenten in der Kontaktkartei anlegen.',
      );
    List<Map<String, dynamic>> inquiries = [];
    try {
      inquiries = businessItems(await session.api.call('/api/inquiries'));
    } on ApiException catch (e) {
      if (e.status != 403) rethrow;
    }
    check(true);
    Map<String, dynamic>? choice;
    await editor(
      'Kunden- und Anfragebezug wählen',
      'sales-choice',
      [
        BusinessField(
          'customer_id',
          'Kontakt',
          type: BusinessInput.choice,
          required: true,
          initial: widget.customerId ?? customers.first['id'],
          choices: {
            for (final item in customers) item['id']: '${item['name']}',
          },
        ),
        BusinessField(
          'inquiry_id',
          'Zugehörige Anfrage',
          type: BusinessInput.choice,
          initial: '',
          choices: {
            '': 'Ohne Anfrage',
            for (final item in inquiries) item['id']: '${item['subject']}',
          },
        ),
      ],
      (values) async {
        choice = values;
      },
    );
    if (choice != null && mounted)
      await edit(
        customerId: choice!['customer_id'],
        inquiryId: choice!['inquiry_id'] == '' ? null : choice!['inquiry_id'],
      );
  }

  Future<void> edit({
    Map<String, dynamic>? previous,
    String? customerId,
    String? inquiryId,
  }) async {
    check(true);
    customerId ??= previous!['customer_id'];
    inquiryId ??= previous?['inquiry_id'];
    final source = businessMap(
      await session.read('/sales/options?customer_id=$customerId'),
    );
    check(true);
    final customer = businessItems(source['customers'])
        .firstWhere((item) => item['id'] == customerId);
    final people = businessItems(source['responsibles']);
    final key = 'sales-save-${previous?['id'] ?? 'new-$customerId'}';
    final fields = [
      const BusinessField('title', 'Verkaufschance', required: true),
      BusinessField(
        'person_id',
        'Ansprechpartner',
        type: BusinessInput.choice,
        initial: '',
        choices: {
          '': 'Kein einzelner Ansprechpartner',
          for (final p in businessItems(customer['persons']))
            p['id']: '${p['name']}',
        },
      ),
      const BusinessField(
        'stage',
        'Vertriebsphase',
        type: BusinessInput.choice,
        initial: 'new',
        choices: salesStages,
      ),
      const BusinessField(
        'expected_net',
        'Erwarteter Nettowert in EUR',
        required: true,
      ),
      const BusinessField(
        'probability_percent',
        'Wahrscheinlichkeit in Prozent',
        type: BusinessInput.integer,
        required: true,
      ),
      BusinessField(
        'responsible_id',
        'Verantwortlich',
        type: BusinessInput.choice,
        required: true,
        initial: people.isNotEmpty ? people.first['id'] : null,
        choices: {for (final p in people) p['id']: '${p['email']}'},
      ),
      const BusinessField(
        'follow_up_on',
        'Wiedervorlage',
        type: BusinessInput.date,
      ),
      const BusinessField(
        'expected_close_on',
        'Erwarteter Abschluss',
        type: BusinessInput.date,
      ),
      const BusinessField(
        'description',
        'Notizen zur Chance',
        type: BusinessInput.multiline,
      ),
      const BusinessField(
        'closure_reason',
        'Grund bei Gewinn oder Verlust',
        type: BusinessInput.multiline,
      ),
    ];
    await editor(
      previous == null
          ? 'Verkaufschance erfassen'
          : 'Verkaufschance bearbeiten',
      key,
      fields,
      (values) async {
        final result = await write(
          key,
          '/sales/opportunities',
          salesValues(
            values,
            customerId: customerId!,
            inquiryId: inquiryId,
            previous: previous,
          ),
        );
        selectedId = result['id'];
      },
      initial: previous == null
          ? {}
          : {
              ...previous,
              'expected_net': (previous['expected_net_minor'] / 100)
                  .toStringAsFixed(2),
            },
    );
    if (mounted) await load();
  }

  Future<void> activity([Map<String, dynamic>? previous]) async {
    final item = selected!;
    final key = 'sales-activity-${previous?['id'] ?? item['id']}';
    await editor(
      previous == null ? 'Aktivität dokumentieren' : 'Aktivität korrigieren',
      key,
      [
        const BusinessField(
          'kind',
          'Art',
          type: BusinessInput.choice,
          initial: 'note',
          choices: {
            'note': 'Notiz',
            'call': 'Telefonat',
            'email': 'E-Mail dokumentieren',
            'meeting': 'Besprechung',
          },
        ),
        BusinessField(
          'occurred_on',
          'Datum',
          type: BusinessInput.date,
          required: true,
          initial: DateTime.now().toUtc().toIso8601String().substring(0, 10),
        ),
        const BusinessField(
          'text',
          'Inhalt',
          type: BusinessInput.multiline,
          required: true,
        ),
        if (previous != null)
          const BusinessField(
            'correction_reason',
            'Korrekturgrund',
            type: BusinessInput.multiline,
            required: true,
          ),
      ],
      (values) async {
        await write(key, '/sales/opportunities/${item['id']}/activities', {
          ...values,
          'supersedes_id': previous?['id'],
          'correction_reason': values['correction_reason'] ?? '',
        });
      },
      initial: previous ?? {},
    );
    if (mounted) await load();
  }

  Future<void> adoptProject() async {
    final item = selected!;
    final key = 'sales-project-${item['id']}';
    await editor(
      'Chance in Projekt übernehmen',
      key,
      [
        BusinessField(
          'project_name',
          'Projektname',
          required: true,
          initial: item['title'],
        ),
        BusinessField(
          'project_id',
          'Projektverknüpfung',
          type: BusinessInput.choice,
          initial: '',
          choices: {
            '': 'Neues Projekt / vorhandenes Anfrageprojekt',
            for (final p in session.projects.where(
              (p) => p['customer_id'] == item['customer_id'],
            ))
              p['id']: '${p['name']}',
          },
        ),
        const BusinessField(
          'confirmation',
          'Ich bestätige Kunde, Chance und Projektübernahme.',
          type: BusinessInput.toggle,
          required: true,
        ),
      ],
      (values) async {
        await write(key, '/sales/opportunities/${item['id']}/project', {
          ...values,
          'project_id': values['project_id'] == ''
              ? null
              : values['project_id'],
          'revision': item['revision'],
          'source_sha256': item['source_sha256'],
        });
      },
    );
    if (mounted) await load();
  }

  Future<void> offer() async {
    check(true);
    final item = selected!, owner = session;
    final key = 'sales-offer-${item['id']}';
    catalogFlow?.dispose();
    final flow = CatalogPriceFlow(
      context,
      owner,
      () =>
          mounted &&
          identical(owner, session) &&
          selected?['id'] == item['id'] &&
          writable &&
          session.canWrite('finance.write') &&
          session.sectionEnabled('documents'),
    );
    catalogFlow = flow;
    try {
      final pending = owner.pendingCommandValues(
        key,
        path: '/sales/opportunities/${item['id']}/offer',
      );
      if (pending != null) {
        await editor(
          'Ursprüngliche Angebotsübernahme prüfen',
          key,
          const [
            BusinessField(
              'confirmation',
              'Exakt den ursprünglichen unbestätigten Auftrag prüfen',
              type: BusinessInput.toggle,
            ),
          ],
          (values) async {
            await flow.fresh();
            if (values['confirmation'] != true)
              throw const FormatException('Prüfung ausdrücklich bestätigen.');
            await write(
              key,
              '/sales/opportunities/${item['id']}/offer',
              pending,
            );
          },
        );
        if (flow.valid) await load();
        return;
      }
      final articles = businessItems(await session.read('/articles'))
          .where((a) => a['active'] == true)
          .toList();
      check(true);
      if (articles.isEmpty)
        throw const FormatException(
          'Zuerst eine aktive Katalogleistung oder einen Artikel anlegen.',
        );
      Map<String, dynamic>? chosen;
      await editor(
        'Katalogpositionen auswählen',
        'sales-offer-choice-${item['id']}',
        [
          BusinessField(
            'articles',
            'Leistungen und Artikel',
            type: BusinessInput.multiple,
            required: true,
            choices: {
              for (final a in articles)
                a['id']:
                    '${a['name']} · ${catalogPriceManaged(a) ? 'Datierter Verkaufspreis erforderlich' : '${a['unit_price_net']} EUR / ${a['unit']} · undatiert (V1)'}',
            },
          ),
        ],
        (values) async {
          chosen = values;
        },
      );
      if (chosen == null || !mounted) return;
      final ids = (chosen!['articles'] as List).cast<String>();
      if (ids.isEmpty || ids.length > 50)
        throw const FormatException('Ein bis 50 Katalogpositionen auswählen.');
      final selectedArticles = articles
          .where((a) => ids.contains(a['id']))
          .toList();
      final priceChoices = <String, CatalogPriceChoice>{};
      for (final article in selectedArticles.where(catalogPriceManaged)) {
        final choice = await flow.choose(article, 'sales_net');
        if (choice == null || !flow.valid) return;
        priceChoices[article['id']] = choice;
      }
      await flow.fresh();
      await editor(
        'Angebotsentwurf aus Katalog erstellen',
        key,
        [
          BusinessField(
            'title',
            'Angebotstitel',
            required: true,
            initial: item['title'],
          ),
          BusinessField(
            'issue_date',
            'Angebotsdatum',
            type: BusinessInput.date,
            required: true,
            initial: DateTime.now().toUtc().toIso8601String().substring(0, 10),
          ),
          const BusinessField(
            'due_date',
            'Gültig bis',
            type: BusinessInput.date,
            required: true,
          ),
          for (final a in selectedArticles)
            BusinessField(
              'quantity_${a['id']}',
              'Menge · ${a['name']}${priceChoices[a['id']] != null ? ' · ${priceChoices[a['id']]!.label}' : ''}',
              type: BusinessInput.decimal,
              required: true,
              initial: '1',
            ),
          const BusinessField(
            'confirmation',
            'Ich bestätige Positionen, Katalogpreise und Angebotsentwurf.',
            type: BusinessInput.toggle,
            required: true,
          ),
        ],
        (values) async {
          await flow.fresh();
          final positions = [
            for (final a in selectedArticles)
              {
                'article_id': a['id'],
                'article_revision': a['revision'],
                'quantity': values['quantity_${a['id']}'],
                if (priceChoices[a['id']] != null)
                  'catalog_price_selection': priceChoices[a['id']]!.selection,
              },
          ];
          await write(key, '/sales/opportunities/${item['id']}/offer', {
            'revision': item['revision'],
            'source_sha256': item['source_sha256'],
            'title': values['title'],
            'issue_date': values['issue_date'],
            'due_date': values['due_date'],
            'confirmation': values['confirmation'],
            'positions': positions,
          });
        },
      );
      if (flow.valid) await load();
    } catch (e) {
      if (flow.valid) rethrow;
    } finally {
      flow.dispose();
      if (identical(catalogFlow, flow)) catalogFlow = null;
    }
  }

  Future<void> history() async {
    final item = selected!;
    final data = businessItems(
      await session.read('/sales/opportunities/${item['id']}/history'),
    );
    check();
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (_) => ListenableBuilder(
        listenable: session,
        builder: (context, _) => AlertDialog(
          title: const Text('Änderungsverlauf'),
          content: SizedBox(
            width: 620,
            child: !allowed
                ? const Text('Zugang nicht mehr verfügbar.')
                : ListView(
                    shrinkWrap: true,
                    children: [
                      for (final row in data)
                        ListTile(
                          title: Text(
                            'Fassung ${row['revision']} · ${salesStages[row['stage']]}',
                          ),
                          subtitle: Text(
                            '${_money(row['expected_net_minor'])} · ${row['probability_percent']} %\nWiedervorlage ${businessDate(row['follow_up_on'])}\n${row['description']}\n${row['closure_reason']}\n${businessDate(row['created_at'], time: true)}',
                          ),
                        ),
                    ],
                  ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Schließen'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> openLink(Map<String, dynamic> link) async {
    if (link['kind'] == 'offer') {
      final scoped = session.sharedProjectSession(link['project_id']);
      await scoped.load();
      check();
      if (!mounted || !scoped.can('finance.read')) return;
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) =>
              BusinessDocumentPage(session: scoped, id: link['document_id']),
        ),
      );
    } else if (widget.onProject != null) {
      final projects = businessItems(await session.api.call('/api/projects'));
      check();
      final project = projects
          .where((value) => value['id'] == link['project_id'])
          .firstOrNull;
      if (project == null) {
        throw const ApiException(
          404,
          'Das verknüpfte Projekt ist nicht mehr verfügbar.',
        );
      }
      widget.onProject!(project);
    }
  }

  Widget detail() {
    final item = selected!;
    final links = businessItems(item['links']);
    final project = links.where((v) => v['kind'] == 'project').firstOrNull;
    final offerLink = links.where((v) => v['kind'] == 'offer').firstOrNull;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(item['title'], style: Theme.of(context).textTheme.headlineMedium),
        Text(
          '${item['customer_name']} · ${item['person_snapshot']?['name'] ?? 'Kein einzelner Ansprechpartner'}',
        ),
        const SizedBox(height: 16),
        Text(
          '${salesStages[item['stage']]} · ${_money(item['expected_net_minor'])} netto erwartet · ${item['probability_percent']} %',
        ),
        Text(
          'Wiedervorlage: ${businessDate(item['follow_up_on'])}${item['overdue'] == true ? ' · überfällig' : ''}',
        ),
        Text('Abschlussziel: ${businessDate(item['expected_close_on'])}'),
        Text(
          'Verantwortlich: ${item['responsible_name'] ?? 'Nicht verfügbar'}',
        ),
        if (item['inquiry_subject'] != null)
          Text('Anfrage: ${item['inquiry_subject']}'),
        if ('${item['description']}'.isNotEmpty) Notice(item['description']),
        if ('${item['closure_reason']}'.isNotEmpty)
          Notice('Abschlussgrund: ${item['closure_reason']}'),
        Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            if (writable)
              OutlinedButton(
                onPressed: () => attempt(() => edit(previous: item)),
                child: const Text('Chance bearbeiten'),
              ),
            OutlinedButton(
              onPressed: () => attempt(history),
              child: const Text('Änderungsverlauf'),
            ),
            if (writable)
              OutlinedButton(
                onPressed: () => attempt(() => activity()),
                child: const Text('Aktivität dokumentieren'),
              ),
            if (project == null && writable && session.can('projects.manage'))
              FilledButton(
                onPressed: () => attempt(adoptProject),
                child: const Text('In Projekt übernehmen'),
              ),
            if (project != null && widget.onProject != null)
              OutlinedButton(
                onPressed: () => attempt(() => openLink(project)),
                child: const Text('Projekt öffnen'),
              ),
            if (offerLink != null && session.can('finance.read'))
              OutlinedButton(
                onPressed: () => attempt(() => openLink(offerLink)),
                child: const Text('Angebot öffnen'),
              ),
            if (project != null &&
                offerLink == null &&
                writable &&
                session.can('finance.write'))
              FilledButton(
                onPressed: () => attempt(offer),
                child: const Text('Angebot aus Katalog erstellen'),
              ),
          ],
        ),
        const SizedBox(height: 24),
        Text(
          'Aktivitäten und Kommunikation',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const Text(
          'Ein dokumentierter E-Mail-Kontakt verschickt keine Nachricht.',
        ),
        if (activities.isEmpty)
          const BusinessEmpty(
            'Noch keine Aktivitäten dokumentiert.',
            'Notizen, Gespräche und Besprechungen erscheinen hier mit ihrem Verlauf.',
          ),
        for (final entry in activities)
          Card(
            child: ListTile(
              title: Text(
                '${({'note': 'Notiz', 'call': 'Telefonat', 'email': 'E-Mail dokumentiert', 'meeting': 'Besprechung'})[entry['kind']]} · ${businessDate(entry['occurred_on'])}',
              ),
              subtitle: Text(
                '${entry['text']}${entry['correction_reason'] == '' ? '' : '\nKorrektur: ${entry['correction_reason']}'}',
              ),
              trailing:
                  writable &&
                      !activities.any((v) => v['supersedes_id'] == entry['id'])
                  ? TextButton(
                      onPressed: () => attempt(() => activity(entry)),
                      child: const Text('Korrigieren'),
                    )
                  : null,
            ),
          ),
      ],
    );
  }

  Widget board() {
    final data = listing!;
    final summary = businessMap(data['summary']);
    final items = businessItems(data);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Notice(
          'Erwartungswerte und gewichtete Beträge sind Vertriebsprognosen. Sie sind keine Umsätze, Zahlungen oder Gewinne.',
        ),
        Text(
          '${summary['open_count']} offene Chancen · ${_money(summary['expected_net_minor'])} erwartet · ${_money(summary['weighted_net_minor'])} gewichtet',
        ),
        Text(
          '${summary['overdue_count']} Wiedervorlagen überfällig · Stand ${businessDate(summary['as_of'], time: true)}',
        ),
        const SizedBox(height: 16),
        TextField(
          controller: query,
          decoration: const InputDecoration(
            labelText: 'Chance oder Kunde suchen',
          ),
          onSubmitted: (_) => load(),
        ),
        DropdownButtonFormField<String>(
          initialValue: stage ?? '',
          decoration: const InputDecoration(labelText: 'Vertriebsphase'),
          items: [
            const DropdownMenuItem(value: '', child: Text('Alle Phasen')),
            for (final entry in salesStages.entries)
              DropdownMenuItem(value: entry.key, child: Text(entry.value)),
          ],
          onChanged: (value) {
            stage = value == '' ? null : value;
            load();
          },
        ),
        if (writable)
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton.icon(
              onPressed: () => attempt(choose),
              icon: const Icon(Icons.add),
              label: const Text('Verkaufschance erfassen'),
            ),
          ),
        for (final phase in salesStages.entries)
          if (stage == null || stage == phase.key) ...[
            const SizedBox(height: 20),
            Text(phase.value, style: Theme.of(context).textTheme.titleLarge),
            if (!items.any((v) => v['stage'] == phase.key))
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('Noch keine Chancen in dieser Phase.'),
              ),
            for (final item in items.where((v) => v['stage'] == phase.key))
              Card(
                child: ListTile(
                  title: Text(item['title']),
                  subtitle: Text(
                    '${item['customer_name']} · ${_money(item['expected_net_minor'])} · ${item['probability_percent']} %\nWiedervorlage ${businessDate(item['follow_up_on'])}${item['overdue'] == true ? ' · überfällig' : ''}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () {
                    selectedId = item['id'];
                    load();
                  },
                ),
              ),
          ],
      ],
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(allowed ? 'Vertriebspipeline' : 'Vertrieb'),
      actions: [
        if (allowed)
          IconButton(
            onPressed: load,
            icon: const Icon(Icons.refresh),
            tooltip: 'Neu laden',
          ),
      ],
    ),
    body: !allowed
        ? const Center(child: Text('Der Zugang ist nicht mehr verfügbar.'))
        : ListView(
            padding: const EdgeInsets.all(24),
            children: [
              if (selectedId != null)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () {
                      selectedId = null;
                      selected = null;
                      load();
                    },
                    icon: const Icon(Icons.arrow_back),
                    label: const Text('Zur Pipeline'),
                  ),
                ),
              if (error != null) Notice(error!, error: true),
              if (loading) const LinearProgressIndicator(),
              if (selectedId == null && listing != null) board(),
              if (selectedId != null && selected != null) detail(),
            ],
          ),
  );
}

import 'package:flutter/material.dart';

import 'business_session.dart';
import 'business_widgets.dart';

Map<String, dynamic> companyOverviewData(dynamic raw) {
  final value = businessMap(raw);
  final finance = businessMap(value['finance']);
  final accounting = businessMap(value['accounting']);
  bool amount(dynamic v) =>
      v == null || v is String && RegExp(r'^-?\d+\.\d{2}$').hasMatch(v);
  if (value['schema_version'] != 1 ||
      !['authorized_projects', 'selected_project'].contains(value['scope']) ||
      value['project_count'] is! int ||
      value['tasks'] is! List ||
      value['appointments'] is! List ||
      finance['projects'] is! List ||
      finance['project_count'] is! int ||
      accounting['available'] is! bool ||
      !RegExp(r'^[a-f0-9]{64}$').hasMatch('${value['source_hash']}') ||
      ![
        'revenue_net',
        'costs_net',
        'contribution_net',
        'receipts_gross',
        'refunds_gross',
        'open_gross',
        'overdue_gross',
      ].every((key) => amount(finance[key]))) {
    throw const FormatException(
      'Die Unternehmensübersicht ist unvollständig. Bitte erneut laden.',
    );
  }
  if (finance['complete_for_recorded_sources'] != true &&
          finance['contribution_net'] != null ||
      finance['project_count'] == 0 && finance['revenue_net'] != null ||
      value['scope'] == 'selected_project' && accounting['available'] == true ||
      accounting['available'] == true &&
          (accounting['balance'] != null ||
              accounting['opening_balances_available'] != false)) {
    throw const FormatException(
      'Die Kennzahlen haben keine eindeutige Berechnungsgrundlage.',
    );
  }
  return value;
}

class BusinessCompanyOverview extends StatelessWidget {
  const BusinessCompanyOverview({
    super.key,
    required this.data,
    required this.onProject,
    required this.onAccounting,
  });
  final Map<String, dynamic> data;
  final void Function(String) onProject;
  final VoidCallback onAccounting;

  @override
  Widget build(BuildContext context) {
    final value = companyOverviewData(data);
    final finance = businessMap(value['finance']),
        accounting = businessMap(value['accounting']);
    Widget metric(String label, String amount, String detail) => SizedBox(
      width: 280,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              Text(amount, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 8),
              Text(detail),
            ],
          ),
        ),
      ),
    );
    Widget source(Map<String, dynamic> item, String title, String detail) =>
        Card(
          child: ListTile(
            title: Text(title),
            subtitle: Text(detail),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => onProject('${item['project_id']}'),
          ),
        );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Datenstand ${businessDate(value['as_of'], time: true)} · ${value['project_count']} freigegebene Projekte',
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            metric(
              'Offene Aufgaben',
              '${value['task_count']}',
              '${value['overdue_task_count']} überfällig',
            ),
            metric(
              'Anstehende Termine',
              '${value['appointment_count']}',
              'Bis ${businessDate(value['appointment_until'])}',
            ),
          ],
        ),
        const SizedBox(height: 16),
        Text('Als Nächstes', style: Theme.of(context).textTheme.titleLarge),
        if ((value['tasks'] as List).isEmpty)
          const Text('Keine offenen Aufgaben.'),
        for (final item in (value['tasks'] as List).map(businessMap))
          source(
            item,
            '${item['title']}',
            '${item['project_name']} · ${businessDate(item['due_date'])}${item['overdue'] == true ? ' · Überfällig' : ''}',
          ),
        if ((value['task_count'] as int) > (value['tasks'] as List).length)
          Text(
            'Die ersten ${(value['tasks'] as List).length} von ${value['task_count']} Aufgaben. Weitere in den Projekten.',
          ),
        const SizedBox(height: 16),
        Text(
          'Anstehende Termine',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        if ((value['appointments'] as List).isEmpty)
          const Text('Keine anstehenden Termine.'),
        for (final item in (value['appointments'] as List).map(businessMap))
          source(
            item,
            '${item['title']}',
            '${item['project_name']} · ${businessDate(item['start_at'], time: true)}',
          ),
        if ((finance['project_count'] as int) > 0) ...[
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              metric(
                'Rechnungsumsatz netto',
                businessMoney(finance['revenue_net']),
                'Festgeschriebene Rechnungen abzüglich Gutschriften',
              ),
              metric(
                'Erfasste Projektkosten netto',
                businessMoney(finance['costs_net']),
                'Material, Arbeit und eingeordnete Eingangsbelege',
              ),
              metric(
                'Projektbeitrag netto',
                finance['contribution_net'] == null
                    ? 'Klärung erforderlich'
                    : businessMoney(finance['contribution_net']),
                'Rechnungsumsatz abzüglich erfasster Projektkosten',
              ),
              metric(
                'Zugeordnete Kundenzahlungen',
                businessMoney(finance['receipts_gross']),
                'Erstattungen ${businessMoney(finance['refunds_gross'])} · jeweils brutto',
              ),
              metric(
                'Offene Kundensalden',
                businessMoney(finance['open_gross']),
                'Davon überfällig ${businessMoney(finance['overdue_gross'])} · jeweils brutto',
              ),
            ],
          ),
          Text(
            'Finanzsicht für ${finance['project_count']} der ${value['project_count']} Projekte. Erfasste Vorgänge seit Beginn; Projektbeiträge enthalten keine unzugeordneten Gemeinkosten.',
          ),
          if (finance['complete_for_recorded_sources'] != true)
            const Text(
              'Kostenquellen sind noch zu klären. Ein vollständiger Projektbeitrag ist deshalb nicht verfügbar.',
            ),
          for (final item in (finance['projects'] as List).map(businessMap))
            source(
              item,
              '${item['project_name']}',
              'Umsatz ${businessMoney(item['revenue_net'])} · Kosten ${businessMoney(item['costs_net'])}${item['complete'] == true ? '' : ' · Prüfung offen'}',
            ),
        ],
        if (accounting['available'] == true) ...[
          const SizedBox(height: 16),
          metric(
            'EÜR ${accounting['year']}',
            accounting['totals']['euer_surplus'] == null
                ? 'Klärung erforderlich'
                : businessMoney(accounting['totals']['euer_surplus']),
            'Bestätigte Einnahmen ${businessMoney(accounting['totals']['confirmed_income'])} · Ausgaben ${businessMoney(accounting['totals']['confirmed_expenses'])} · ${accounting['issue_count']} Prüfpunkte',
          ),
          Text(
            'Erfasste Buchungen · Buchführungsbeginn ${businessDate(accounting['coverage_start'])}',
          ),
          FilledButton(
            onPressed: onAccounting,
            child: const Text('EÜR und Belege öffnen'),
          ),
          const SizedBox(height: 16),
          Text(
            'Erfasste Geldbewegungen',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const Text(
            'Anfangsbestände sind noch nicht hinterlegt. Ein aktueller Kontostand ist daher nicht verfügbar.',
          ),
          for (final item in (accounting['account_movements'] as List).map(
            businessMap,
          ))
            ListTile(
              title: Text(
                '${item['account']['name'] ?? item['account']['id']}',
              ),
              subtitle: Text(
                'Zuflüsse ${businessMoney(item['inflows'])} · Abflüsse ${businessMoney(item['outflows'])} · Veränderung ${businessMoney(item['movement_net'])}',
              ),
            ),
        ],
        const SizedBox(height: 24),
      ],
    );
  }
}

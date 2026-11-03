"""Read-only overview composed from authorized domain sources, never estimates."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from zoneinfo import ZoneInfo

from core import Problem, canonical
from business_foundation import BusinessFoundation, _fresh, _id
from business_operations import transaction, money
from business_schema import state


def overview_metrics(office, actor, query=None, *, clock=lambda: datetime.now(timezone.utc)):
    query = query or {}
    if not isinstance(query, dict) or set(query) - {'project_id'}:
        raise Problem(400, 'Nur ein optionales Projekt für die Übersicht angeben.')
    selected = _id(query['project_id']) if 'project_id' in query else None
    now = clock().astimezone(timezone.utc)
    today = now.astimezone(ZoneInfo('Europe/Berlin')).date()
    until = today + timedelta(days=30)
    from project_workspace import ProjectWorkspace
    from business_planning import Planning
    from business_project_economics import ProjectEconomics
    from business_finance import Finance
    with transaction(office):
        actor = _fresh(office, actor)
        foundation = BusinessFoundation(office)
        projects = ([foundation.project(actor, selected)] if selected else foundation.pipeline(actor)['items'])
        environment = state(office)
        modules = set(environment['read_capabilities'])
        tasks, appointments, financial, warnings = [], [], [], []
        financial_ids, planning_ids = [], []
        workspace = ProjectWorkspace(office)
        for project in projects:
            identifier = project['id']
            for item in workspace.list_items(actor, identifier, 'tasks'):
                if item['status'] in ('done', 'cancelled'):
                    continue
                tasks.append(dict(id=item['id'], project_id=identifier, project_name=project['name'],
                    title=item['title'], due_date=item['due_date'], priority=item['priority'],
                    overdue=bool(item['due_date'] and item['due_date'] < today.isoformat()),
                    source_path=f'/projects/{identifier}/tasks/{item["id"]}'))
            if 'business_planning' in modules:
                try:
                    foundation.authorize(actor, 'planning.read', identifier)
                    planning_ids.append(identifier)
                    schedule = Planning(office, clock=clock).appointments(actor, dict(project_id=identifier,
                        **{'from': today.isoformat(), 'to': until.isoformat()}))['items']
                    for item in schedule:
                        if item['project_id'] != identifier or item['status'] == 'cancelled' or datetime.fromisoformat(item['end_at']) < now:
                            continue
                        appointments.append(dict(id=item['id'], project_id=identifier, project_name=project['name'],
                            title=item['title'], start_at=item['start_at'], end_at=item['end_at'],
                            source_path='/business/appointments/' + item['id']))
                except Problem as error:
                    if error.status not in (403, 404):
                        raise
            if 'business_project_economics' in modules:
                try:
                    foundation.authorize(actor, 'finance.read', identifier)
                    values = ProjectEconomics(office).summary(actor, identifier)
                    outstanding = Finance(office, clock=clock).open_items(actor, identifier)['items']
                    overdue = [item for item in outstanding if item['overdue_days'] > 0 and Decimal(item['open']) > 0]
                    financial.append(dict(project_id=identifier, project_name=project['name'],
                        revenue_net=values['revenue']['revenue_net'], costs_net=values['costs']['total_net'],
                        contribution_net=values['result']['document_net_contribution'],
                        complete=values['result']['complete_for_recorded_sources'],
                        receipts_gross=values['payments']['receipts_gross'], refunds_gross=values['payments']['refunds_gross'],
                        open_gross=values['payments']['open_gross'],
                        overdue_gross=money(sum((Decimal(item['open']) for item in overdue), Decimal(0))),
                        overdue_count=len(overdue), issue_count=len(values['issues']),
                        source_path='/business/project-economics?project_id=' + identifier))
                    financial_ids.append(identifier)
                    if not values['result']['complete_for_recorded_sources']:
                        warnings.append(dict(code='project_costs_incomplete', project_id=identifier,
                            message='Kostenquellen prüfen; das Projektergebnis ist noch unvollständig.'))
                except Problem as error:
                    if error.status not in (403, 404):
                        raise
        def total(field):
            return money(sum((Decimal(item[field]) for item in financial), Decimal(0))) if financial else None
        complete = bool(financial) and all(item['complete'] for item in financial)
        finance = dict(scope='authorized_project_recorded_sources', project_count=len(financial),
            complete_for_recorded_sources=complete, currency='EUR',
            **{field: total(field) for field in ('revenue_net', 'costs_net', 'receipts_gross', 'refunds_gross', 'open_gross', 'overdue_gross')},
            contribution_net=total('contribution_net') if complete else None,
            overdue_count=sum(item['overdue_count'] for item in financial), projects=financial)
        accounting = dict(available=False)
        if not selected and 'business_accounting_euer' in modules:
            from business_accounting_euer import EuerAccounting
            try:
                service = EuerAccounting(office)
                report = service.report(actor, today.year)
                catalog = service.sources(actor)
                accounting = dict(available=True, year=today.year, scope=report['scope'],
                    complete_for_recorded_sources=report['complete_for_recorded_sources'],
                    totals=report['totals'], issue_count=len(report['issues']), state_hash=report['state_hash'],
                    coverage_start=report['coverage_start'], source_path='/business/accounting/euer/report?year=' + str(today.year),
                    account_movements=catalog['account_movements'], opening_balances_available=False,
                    balance=None, cash_scope=catalog['cash_scope'])
            except Problem as error:
                if error.status not in (403, 404):
                    raise
        # Repeat every source permission after composition. Never publish a
        # source read before a concurrently committed rights revocation.
        for project in projects:
            foundation.project(actor, project['id'])
        for identifier in financial_ids:
            foundation.authorize(actor, 'finance.read', identifier)
        for identifier in planning_ids:
            foundation.authorize(actor, 'planning.read', identifier)
        if accounting['available']:
            service._access(actor)
        tasks.sort(key=lambda item: (not item['overdue'], item['due_date'] or '9999', item['priority'] != 'high', item['id']))
        appointments.sort(key=lambda item: (item['start_at'], item['id']))
        value = dict(schema_version=1, scope='selected_project' if selected else 'authorized_projects',
            project_id=selected, project_count=len(projects), reporting_date=today.isoformat(),
            task_count=len(tasks), overdue_task_count=sum(item['overdue'] for item in tasks),
            tasks=tasks[:20], task_limit=20, appointment_count=len(appointments), appointments=appointments[:10],
            appointment_limit=10, appointment_until=until.isoformat(), finance=finance, accounting=accounting, warnings=warnings)
        value['source_hash'] = hashlib.sha256(canonical(value).encode()).hexdigest()
        value['as_of'] = now.isoformat()
        return value

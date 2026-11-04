"""Additive business routing; modules own short authorized transactions.

The public Gmail/SPIN receiver is deliberately outside this namespace. Import
names are source-controlled; neither requests nor database rows select Python
modules. Provider I/O and rendering must not run inside a global Office lock.
"""
import importlib
import json
import re
from core import Problem

MODULES = (
    'business_foundation', 'business_documents', 'business_finance',
    'business_planning', 'business_time', 'business_operations',
    'business_inventory', 'business_maintenance', 'business_adapters', 'business_catalog_imports', 'business_catalog_prices', 'business_organization', 'business_purchasing', 'business_portal',
    'business_accounting', 'business_accounting_allocations', 'business_accounting_components', 'business_accounting_refunds', 'business_accounting_capacity',
    'business_accounting_refunds_v2',
    'business_accounting_profile',
    'business_project_economics', 'business_asset_provenance', 'business_customer_workspace', 'business_personnel_workflow', 'business_accounting_euer', 'business_assistant', 'business_payroll', 'business_inventory_counts', 'business_sales', 'business_payroll_accounts', 'business_assistant_speech', 'business_company_handover', 'business_migrations', 'business_custom_fields', 'business_privacy_cases', 'business_payroll_cash', 'business_service', 'business_bank_reconciliation', 'business_resource_custody', 'business_purchase_changes', 'business_payroll_facts', 'business_travel_allowances', 'business_payroll_entitlements', 'business_payroll_calculation_cases', 'business_payroll_annual_basis', 'business_payroll_wage_interruptions', 'business_payroll_oneoff_cases', 'business_payroll_multiple_cases', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items', 'business_company_events', 'business_accounting_year_openings',
)


def _modules():
    for name in MODULES:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError as error:
            if error.name != name:
                raise
            continue
        yield module


def _relative(path):
    return path[len('/business'):] if isinstance(path, str) and path.startswith('/business/') else None


def _method_string(value):
    if value is None:
        return None
    values = value.split(', ') if isinstance(value, str) else value
    if not isinstance(values, (list, tuple, set, frozenset)) or any(v not in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH') for v in values):
        raise RuntimeError('Invalid business module method contract')
    return ', '.join(v for v in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE') if v in values)


def methods(path):
    relative = _relative(path)
    if relative is None:
        return None
    if relative == '/capabilities':
        return 'GET'
    if relative == '/offline/access':
        return 'POST'
    for module in _modules():
        classify = getattr(module, 'methods', None)
        if classify:
            result = _method_string(classify(relative))
            if result is not None:
                return result
    return None


def query_data(pairs):
    query = {}
    for key, value in pairs:
        if (not isinstance(key, str) or not isinstance(value, str) or
                key in query or len(key) > 80 or len(value) > 4096 or len(query) >= 25):
            raise Problem(400, 'Ungültiger Suchfilter.')
        query[key] = value
    return {'_query': query} if query else {}


def offline_path(path, method, scopes=None):
    scopes = {'time_events', 'field_media', 'offline_reports'} if scopes is None else set(scopes)
    if path == '/business/capabilities' and method == 'GET':
        return True
    if 'time_events' in scopes and ((path == '/business/time/events' and method == 'POST') or
            (method == 'GET' and isinstance(path, str) and re.fullmatch(r'/business/time/entries/[a-f0-9]{32}', path))):
        return True
    if 'field_media' in scopes:
        if path == '/business/media' and method == 'POST':
            return True
        if isinstance(path, str) and re.fullmatch(r'/business/media/[a-f0-9]{32}(?:/content)?', path) and method == 'GET':
            return True
        if isinstance(path, str) and re.fullmatch(r'/business/media/[a-f0-9]{32}/(?:chunks/[0-9]{1,3}|complete)', path) and method == 'POST':
            return True
    if 'offline_reports' in scopes:
        if path == '/business/service-reports/offline' and method == 'POST':
            return True
        if method == 'GET' and isinstance(path, str) and re.fullmatch(r'/business/service-reports/[a-f0-9]{32}(?:/pdf)?', path):
            return True
    return False


def strict_report_path(path):
    """Framing for the capture command and individual signed archive reads."""
    return path == '/business/service-reports/offline' or (
        isinstance(path, str) and re.fullmatch(r'/business/service-reports/[a-f0-9]{32}(?:/pdf)?', path) is not None)


def strict_workflow_path(path):
    """Explicit workflow commands must not silently ignore another input channel."""
    if not isinstance(path, str):
        return False
    return re.fullmatch(
        r'/business/(?:(?:project-economics|customer-workspace|receipt-media|personnel|payroll|accounting/euer|accounting/opening-balances|accounting/historical-assets|accounting/open-items|accounting/year-values|assistant|company-events|sales|company-handover|migrations|custom-fields|privacy/cases|service|bank|resource-custody|catalog-prices)(?:/.*)?|overview/metrics|inventory/(?:counts(?:/.*)?|count-sources)|'
        r'finance/receipts(?:/[a-f0-9]{32}(?:/original)?)?|adapters(?:/.*)?|'
        r'assets/(?:from-delivery|origin-sources|[a-f0-9]{32}/origin)|'
        r'purchasing/orders/[a-f0-9]{32}/(?:changes|change-files(?:/[a-f0-9]{32}/original)?|amendments(?:/preview)?|supplier-returns(?:/preview)?)|'
        r'purchasing/receipts/[a-f0-9]{32}/document)', path) is not None


def decode_offline_report(raw, *, max_bytes=1_000_000):
    """One unambiguous UTF-8 signature envelope on both transports."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate field')
            result[key] = value
        return result

    def constant(value):
        raise ValueError('Nonfinite number')

    try:
        if not isinstance(raw, bytes) or not 0 < len(raw) <= max_bytes:
            raise Problem(413, 'Anfrage zu groß oder leer')
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        if not isinstance(result, dict):
            raise ValueError('Expected object')
        return result
    except (UnicodeError, ValueError, RecursionError):
        raise Problem(400, 'Eindeutiges UTF-8-JSON-Objekt erwartet.') from None


def _report_access(office, actor, state):
    """Current project hints; authorization is repeated at every domain write.

    Pausing a module only suspends writes, so devices can retain their original
    queue without mistaking a pause for a revoked project permission.
    """
    from business_foundation import _fresh, require_permission
    from business_organization import module_enabled
    actor = _fresh(office, actor)
    readable = set(state.get('read_capabilities', []))
    project_ids = []
    if 'business_operations' in readable:
        for project in office.projects(actor):
            try:
                require_permission(office, actor, 'documents.read', project['id'])
                require_permission(office, actor, 'documents.write', project['id'])
            except Problem as error:
                if error.status not in (403, 404):
                    raise
            else:
                project_ids.append(project['id'])
    enabled = (not state.get('readonly', True) and
               'business_operations' in state.get('active_capabilities', state.get('capabilities', [])))
    if 'business_organization' in readable:
        enabled = enabled and module_enabled(office, 'documents')
    return {'report_project_ids': sorted(project_ids), 'report_writes_enabled': bool(enabled)}


def capabilities(office, actor, project_id=None):
    import business_schema
    from business_foundation import permissions
    with office.lock, office.db:
        state = business_schema.state(office)
        active = state.get('compatibility_mode') == 'business'
        modules = [module for module in _modules()
                   if callable(getattr(module, 'dispatch', None))]
        available = {module.__name__ for module in modules}
        configured = state.get('capabilities', []) if active else state.get('read_capabilities', [])
        values = [value if value.startswith('business_') else 'business_' + value for value in configured]
        supported_modules = set(values) & available
        features = set()
        for module in modules:
            if module.__name__ not in supported_modules:
                continue
            declared = getattr(module, 'FEATURES', ())
            if not isinstance(declared, (tuple, list)) or any(
                    not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{2,40}', name)
                    for name in declared):
                raise RuntimeError('Invalid packaged business feature declaration')
            select_features = getattr(module, 'runtime_features', None)
            offered = select_features(office) if select_features is not None else declared
            if (not isinstance(offered, (tuple, list, set, frozenset))
                    or any(name not in declared for name in offered)):
                raise RuntimeError('Invalid runtime business feature declaration')
            features.update(offered)
        global_permissions = sorted(permissions(office, actor)) if state.get('storage_version') == 7 else []
        effective = global_permissions
        if project_id is not None:
            from business_foundation import project_permissions
            effective = sorted(project_permissions(office, actor, project_id))
        organization = {}
        if 'business_organization' in supported_modules:
            from business_organization import navigation
            organization = {'organization': navigation(office, actor)}
        return {**state, **organization,
                'capabilities': sorted(supported_modules), 'features': sorted(features),
                'active_capabilities': state.get('capabilities', []),
                'permissions': effective, 'global_permissions': global_permissions,
                'project_id': project_id}


def _dispatch(office, actor, path, method, data, *, offline=False, offline_capabilities=()):
    relative = _relative(path)
    if relative is None:
        return None
    if offline and not offline_path(path, method, offline_capabilities):
        raise Problem(403, 'Dieser Gerätezugang erlaubt nur ausdrücklich freigegebene Baustellenfunktionen.')
    if relative == '/capabilities':
        if method != 'GET':
            raise Problem(405, 'HTTP-Methode nicht erlaubt.')
        result = capabilities(office, actor, data.get('_query', {}).get('project_id'))
        if offline:
            result.pop('organization', None)
            result['features'] = []
            result['permissions'] = [p for p in result['permissions'] if p in ('time.own', 'documents.read', 'documents.write')]
            result['global_permissions'] = result['permissions']
            result['capabilities'] = [p for p in result['capabilities'] if
                (p == 'business_time' and 'time_events' in offline_capabilities) or
                (p == 'business_operations' and set(offline_capabilities) & {'field_media', 'offline_reports'})]
            permitted_modules = {name for name, scope in (('business_time', 'time_events'),
                ('business_operations', 'field_media'), ('business_operations', 'offline_reports')) if scope in offline_capabilities}
            if 'offline_reports' in offline_capabilities:
                result.update(_report_access(office, actor, result))
            for key in ('active_capabilities', 'read_capabilities'):
                result[key] = [name for name in result.get(key, []) if name in permitted_modules]
            result.pop('restore_id', None)
        return result, 200, 'application/json'
    if relative == '/offline/access':
        if offline or method != 'POST' or data:
            raise Problem(400, 'Leerer ausdrücklicher Geräteauftrag erwartet.')
        import business_schema
        import plan_access
        from business_foundation import require_permission
        with office.lock, office.db:
            state = business_schema.state(office)
            active = set(state.get('capabilities', []))
            caps = []
            from business_foundation import permissions
            allowed = permissions(office, actor)
            if 'business_time' in active and 'time.own' in allowed:
                caps.append('time_events')
            if 'business_operations' in active and 'documents.write' in allowed:
                caps.append('field_media')
            reports = _report_access(office, actor, state)
            if reports['report_writes_enabled'] and reports['report_project_ids']:
                caps.append('offline_reports')
            if not caps:
                raise Problem(403, 'Keine freigegebenen Baustellenfunktionen verfügbar.')
            return {**plan_access.issue(office, actor, workspace=True, business=True, business_capabilities=caps),
                    **reports,
                    'capabilities': ['project_plans', 'offline_plan_access', 'plan_imports',
                                     'plan_deletion', 'project_workspace', 'offline_workspace', *caps]}, 201, 'application/json'
    import business_schema
    for module in _modules():
        classify = getattr(module, 'methods', None)
        handler = getattr(module, 'dispatch', None)
        if not classify or not handler or classify(relative) is None:
            continue
        if method not in _method_string(classify(relative)).split(', '):
            raise Problem(405, 'HTTP-Methode nicht erlaubt.')
        current = business_schema.state(office)
        active = current.get('capabilities', [])
        readable = current.get('read_capabilities', [])
        security_revoke = (method == 'POST' and (
            module.__name__ == 'business_portal'
            and re.fullmatch(r'/portal/grants/[a-f0-9]{32}/revoke', relative) is not None
            or module.__name__ == 'business_customer_workspace'
            and re.fullmatch(r'/customer-workspace/(?:grants|files)/[a-f0-9]{32}/revoke', relative) is not None))
        catalog_preview = (method == 'POST' and module.__name__ == 'business_catalog_imports'
                           and re.fullmatch(r'/adapters/imports/[a-f0-9]{32}/catalog-preview', relative) is not None
                           or method == 'POST' and module.__name__ == 'business_catalog_prices'
                           and re.fullmatch(r'/catalog-prices/(?:candidates|imports/[a-f0-9]{32}/preview)', relative) is not None)
        if module.__name__ not in active and not ((method == 'GET' or security_revoke or catalog_preview) and module.__name__ in readable):
            raise Problem(409, 'Dieses Modul ist im aktuellen Betriebsmodus nicht schreibend freigegeben.')
        if method != 'GET' and not catalog_preview and 'business_organization' in readable:
            from business_organization import require_active
            require_active(office, actor, relative, module.__name__, data)
        result = handler(office, actor, relative, method, data)
        if result is not None:
            return result
    raise Problem(404, 'Funktion nicht gefunden.')


_TIME_ENTRY_FIELDS = frozenset(('id', 'employee_id', 'project_id', 'category_id',
    'status', 'started_at', 'start_at', 'ended_at', 'last_at', 'timezone', 'revision',
    'last_sequence', 'sequence', 'updated_at', 'worked_seconds', 'break_seconds', 'events'))


def _time_payload(value):
    if not isinstance(value, dict):
        raise Problem(500, 'Ungültiger Zeitbeleg.')
    result = {key: value[key] for key in _TIME_ENTRY_FIELDS if key in value}
    if 'events' in result:
        result['events'] = [{key: event[key] for key in ('id', 'action', 'occurred_at',
            'received_at', 'device_id', 'sequence') if key in event} for event in result['events']]
    return result


def dispatch(office, actor, path, method, data, *, offline=False, offline_capabilities=()):
    if not offline:
        return _dispatch(office, actor, path, method, data)
    if not offline_path(path, method, offline_capabilities):
        raise Problem(403, 'Dieser Gerätezugang erlaubt nur ausdrücklich freigegebene Baustellenfunktionen.')
    if path.startswith('/business/service-reports/'):
        # Rendering owns two short domain transactions. Never wrap this command
        # in the shared time/media lock or a surrounding database transaction.
        from business_foundation import require_permission
        from business_operations import own_offline_report
        try:
            with office.lock:
                if method == 'GET':
                    if data:
                        raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
                    entry_id = path.split('/')[3]
                    if not own_offline_report(office, actor, entry_id):
                        raise Problem(403, 'Eigenes Offline-Protokoll nicht verfügbar.')
                else:
                    if not isinstance(data, dict) or '_query' in data:
                        raise Problem(400, 'Unveränderte Offline-Erfassung erwartet.')
                    project_id = data.get('project_id')
                    require_permission(office, actor, 'documents.read', project_id)
                    require_permission(office, actor, 'documents.write', project_id)
            return _dispatch(office, actor, path, method, data, offline=True, offline_capabilities=offline_capabilities)
        except Problem as error:
            if error.status == 404:
                raise Problem(403, 'Eigenes Offline-Protokoll oder Projekt nicht verfügbar.') from None
            raise
    # The narrow time path does no provider I/O or rendering. Hold its ownership
    # check through the event's nested transaction to close cross-entry races.
    with office.lock, office.db:
        from business_time import TimeTracking
        from business_foundation import require_permission
        if path == '/business/capabilities':
            return _dispatch(office, actor, path, method, data, offline=True, offline_capabilities=offline_capabilities)
        if path.startswith('/business/media'):
            from business_operations import own_operational_photo
            fresh = require_permission(office, actor, 'documents.write' if method == 'POST' else 'documents.read')
            if path == '/business/media':
                if (data.get('media_type') not in ('image/jpeg', 'image/png') or
                        data.get('purpose', 'site_photo') != 'site_photo' or
                        data.get('classification', 'operational') != 'operational'):
                    raise Problem(403, 'Der Gerätezugang erlaubt ausschließlich eigene operative Fotos.')
            else:
                match = re.fullmatch(r'/business/media/([a-f0-9]{32})(?:/.*)?', path)
                if not match or not own_operational_photo(office, actor, match[1]):
                    raise Problem(404, 'Foto nicht verfügbar.')
            return _dispatch(office, fresh, path, method, data, offline=True, offline_capabilities=offline_capabilities)
        fresh = require_permission(office, actor, 'time.own')
        service = TimeTracking(office)
        employee = data.get('employee_id')
        if employee is not None and not service.owns_employee(fresh, employee):
            raise Problem(403, 'Der Gerätezugang gilt nur für eigene Zeiten.')
        match = re.fullmatch(r'/business/time/entries/([a-f0-9]{32})', path)
        entry = match[1] if match else data.get('entry_id')
        if entry is not None:
            if not isinstance(entry, str) or not re.fullmatch(r'[a-f0-9]{32}', entry):
                raise Problem(400, 'Ungültiger Zeitbeleg.')
            row = office.db.execute('SELECT employee_id FROM business_time_entries WHERE id=?', (entry,)).fetchone()
            if row is not None and not service.owns_employee(fresh, row['employee_id']):
                raise Problem(404, 'Zeitbeleg nicht verfügbar.')
        result, status, media = _dispatch(office, fresh, path, method, data, offline=True, offline_capabilities=offline_capabilities)
        if path != '/business/capabilities':
            if 'entry' in result:
                result = {key: result[key] for key in ('entry', 'event_id', 'request_id', 'idempotent') if key in result}
                result['entry'] = _time_payload(result['entry'])
            else:
                result = _time_payload(result)
        return result, status, media


def document_policy_installed(office):
    """Installed classification decisions stay enforced in compatibility mode."""
    import business_schema
    return 'business_document_classes' in business_schema._tables(office)


def can_read_document(office, actor, project, kind, identifier, category=None):
    if not document_policy_installed(office):
        return True  # Explicit pre-migration compatibility, not a new grant.
    from business_foundation import BusinessFoundation
    return BusinessFoundation(office).can_read_document(actor, project, kind, identifier, category)


def require_document(office, actor, project, kind, identifier, category=None):
    if not can_read_document(office, actor, project, kind, identifier, category):
        raise Problem(404, 'Dokument nicht verfügbar.')


def require_link_write(office, actor, project, identifier=None, category=None):
    if not document_policy_installed(office):
        return
    from business_foundation import BusinessFoundation, require_permission
    if category in ('offer', 'invoice'):
        require_permission(office, actor, 'finance.write', project)
    if identifier is not None:
        record = BusinessFoundation(office).classification(actor, project, 'link', identifier)
        level = record['effective_classification']
        if level == 'financial':
            require_permission(office, actor, 'finance.write', project)
        elif level == 'personnel':
            require_permission(office, actor, 'personnel.manage', project)
        elif level in ('restricted', 'unclassified'):
            require_permission(office, actor, 'documents.classify', project)

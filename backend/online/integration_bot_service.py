"""Scoped metadata delivery through the user's existing Calendar/OneDrive bot.

The bot receives only queued read requests. It cannot access application
customers, finance, sessions, mail intake or change upstream calendars/files.
Provider account identity, project selection and generation remain explicit.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import hmac
import re
import secrets

from core import Problem, canonical, digest
from integration_bridge import IntegrationBridgeJobs, ERROR_CODES
from online.integrations_service import _object, _request_id, _text, _generation, _revision, _selection


BOT_PROVIDERS = ('google_calendar', 'onedrive')
KEY_TTL = 90 * 86400
BOOTSTRAP_TTL = 300
FRESH_SECONDS = 300
BOT_ERRORS = {
    'provider_unavailable': 'Der Bot konnte den Anbieter nicht erreichen.',
    'reconnect_required': 'Die Anbieterverbindung des Bots muss erneuert werden.',
    'rate_limited': 'Der Anbieter begrenzt die Abrufe. Bitte später erneut versuchen.',
    'timeout': 'Der Bot konnte den Abruf nicht rechtzeitig abschließen.',
    'invalid_response': 'Der Bot hat keine vollständigen gültigen Quelldaten erhalten.',
    'not_found': 'Die gewählte Quelle ist beim Anbieter nicht mehr verfügbar.',
    'permission_denied': 'Dem Bot fehlt die Lesefreigabe für die gewählte Quelle.',
    'unsupported': 'Das verbundene Botwerkzeug kann die angeforderten Metadaten nicht liefern.',
    'resource_too_large': 'Die Auswahl ist zu umfangreich. Bitte einen kleineren Kalenderumfang oder Projektunterordner wählen.',
}


def _iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec='seconds')


class BotIntegrations:
    def __init__(self, parent):
        self.parent, self.office, self.domain = parent, parent.office, parent.domain
        self.jobs = IntegrationBridgeJobs(self.office, clock=parent.clock)

    def _config(self, row):
        if not row.get('config'):
            return {}
        try:
            return self.parent._decrypt(row['config'])
        except Problem:
            return {}

    def mode(self, row):
        return row['provider'] == 'onedrive' or self._config(row).get('mode') == 'bot'

    def active(self, token, provider, project=None):
        if provider not in BOT_PROVIDERS:
            return False
        with self.office.lock, self.office.db:
            actor = self.parent._actor(token, owner=project is None)
            row = self.parent._connection(actor, provider, project)
            return self.mode(row)

    def instructions(self):
        base = 'https://' + self.parent.host + '/api/v1/intake/integrations/jobs'
        return (
            'Ergänze den bestehenden Fünfminutenjob um Smartplan-Projektaufträge. '
            'Behalte den Gmail-SPIN-Zugang, die Mailbestätigungen und alle Filter; '
            'lege keinen zweiten Job an. Nutze die bereits verbundenen Google-Kalender- '
            'und OneDrive-Werkzeuge ausschließlich lesend. Hinterlege den neuen '
            'SPIX-Zugang geschützt als SMARTPLAN_INTEGRATION_TOKEN, nicht im Chat. '
            'Lies offene Aufträge per GET ' + base + ' mit geschützter Bearer-Bindung. '
            'Liefere ausschließlich die angeforderten Originalmetadaten gemäß dem '
            'beigefügten Projektbot-Vertrag an den festen Ergebnisendpunkt. '
            'Erhalte originale Konto-, Kalender-, Termin-, Laufwerk- und Datei-IDs, '
            'Zeitzonen und Quellenrevisionen. Führe Inhalte oder Links nicht aus. '
            'Keine Termine anlegen, Einladungen senden, Freigaben erstellen, Dateien '
            'verschieben oder Unterlagen extern analysieren. Fehlender Zugriff ist '
            'ein Fehler und keine leere erfolgreiche Auswahl. Erst HTTP 201 mit '
            'status received und passender job_id bestätigt die Lieferung.'
        )

    def _latest_task(self, row, kind, resource=None):
        comparison = 'resource IS NULL' if resource is None else 'resource=?'
        parameters = (row['provider'], row['generation'], row.get('owner_id'), kind)
        if resource is not None:
            parameters += (resource,)
        return self.office.db.execute(
            'SELECT status,error_code,created_at,expires_at FROM external_bridge_jobs '
            'WHERE provider=? AND generation=? AND owner_id=? AND kind=? AND ' +
            comparison + " ORDER BY created_at DESC, CASE WHEN status='pending' THEN 1 ELSE 0 END DESC,"
            'completed_at DESC,id DESC LIMIT 1', parameters,
        ).fetchone()

    def _task_error(self, task):
        if task is None:
            return None
        if task['status'] == 'failed':
            return BOT_ERRORS.get(task['error_code'], 'Der Bot konnte den Abruf nicht abschließen.')
        if task['status'] == 'expired' or (
                task['status'] == 'pending' and task['expires_at'] <= self.parent.clock()):
            return 'Der Bot hat diesen Abruf noch nicht bestätigt. Bitte Botverbindung und Fünfminutenjob prüfen.'
        return None

    def _resource_failure(self, row, resource, confirmed):
        failed = self.office.db.execute(
            "SELECT status,error_code,created_at,expires_at FROM external_bridge_jobs "
            "WHERE provider=? AND generation=? AND owner_id=? AND kind='resource' AND resource=? "
            "AND status='failed' ORDER BY created_at DESC,completed_at DESC,id DESC LIMIT 1",
            (row['provider'], row['generation'], row['owner_id'], resource),
        ).fetchone()
        if failed and (confirmed is None or failed['created_at'] > confirmed['created_at']):
            return self._task_error(failed)
        return None

    def public_status(self, row):
        config = self._config(row)
        result = {'method': 'bot', 'instructions': self.instructions(),
                  'scopes': ['Nur angeforderte Kalender- und OneDrive-Projektmetadaten'],
                  'redirect_uri': None, 'expires_at': None}
        if config.get('mode') != 'bot':
            return result
        if row['state'] == 'configured':
            result.update(state='awaiting_bot', connected=False)
        expiry = config.get('expires_at')
        if isinstance(expiry, (int, float)):
            result['expires_at'] = _iso(expiry)
            if expiry <= self.parent.clock():
                result.update(state='key_expired', error='Der Botzugang ist abgelaufen. Bitte einen neuen Schlüssel erstellen.')
        if result.get('state') != 'key_expired':
            failure = self._task_error(self._latest_task(row, 'catalog'))
            if failure:
                result.update(state='error', error=failure)
        try:
            actor = {'id': row['owner_id']}
            last = self.jobs.latest(actor, row['provider'], 'catalog', None, generation=row['generation'])
            if last:
                result['last_sync'] = _iso(last['completed_at'])
        except Problem:
            pass
        return result

    def project_public_status(self, actor, project, row, binding):
        result = {'method': 'bot'}
        config = self._config(row)
        if config.get('mode') == 'bot' and config.get('expires_at', 0) <= self.parent.clock():
            return dict(result, state='key_expired',
                        error='Der Botzugang ist abgelaufen. Die Aktualisierung ist pausiert.')
        if row['state'] == 'configured':
            return dict(result, state='awaiting_bot', connected=False, data=None, binding=None)
        if row['state'] != 'connected':
            return result
        if binding and binding.get('data'):
            pending = self.office.db.execute(
                "SELECT id FROM external_bridge_jobs WHERE provider=? AND project_id=? "
                "AND kind='snapshot' AND generation=? AND revision=? AND status='pending' AND expires_at>? LIMIT 1",
                (row['provider'], project, row['generation'], binding['revision'], self.parent.clock()),
            ).fetchone()
            if pending:
                result.update(state='sync_pending', job_id=pending['id'],
                              message='Abgleich angefordert. Der Bot liefert beim nächsten Lauf.')
        return result

    def connect(self, token, data):
        _object(data, ('request_id',), ('request_id',))
        request = _request_id(data)
        with ExitStack() as operations:
            for provider in BOT_PROVIDERS:
                operations.enter_context(self.parent._operation(provider))
            with self.office.lock, self.office.db:
                actor = self.parent._actor(token, owner=True)
                rows = [self.domain.connection(actor, p) for p in BOT_PROVIDERS]
                configs = [self._config(row) for row in rows]
                markers = {provider: digest(canonical(['project-bot', provider, request]))[:32]
                           for provider in BOT_PROVIDERS}
                seen = any(self.office.db.execute(
                    'SELECT 1 FROM external_requests WHERE user_id=? AND request_id=?',
                    (actor['id'], marker),
                ).fetchone() is not None for marker in markers.values())
                matching = [config.get('request_id') == request for config in configs]
                if any(matching):
                    if not all(matching):
                        raise Problem(409, 'Die Botverbindung wurde inzwischen geändert. Bitte neu laden.')
                    raw = configs[0].get('bootstrap_token')
                    if (not isinstance(raw, str) or
                            any(row['owner_id'] != actor['id'] or cfg.get('mode') != 'bot' or
                                cfg.get('bootstrap_until', 0) <= self.parent.clock() or
                                cfg.get('token_hash') != digest(raw) for row, cfg in zip(rows, configs))):
                        raise Problem(409, 'Der Schlüssel wurde bereits ausgegeben. Bei Bedarf ausdrücklich einen neuen erstellen.')
                    expiry = configs[0]['expires_at']
                else:
                    if seen:
                        raise Problem(409, 'Dieser Schlüsselauftrag wurde inzwischen abgelöst. Bitte den aktuellen Stand neu laden.')
                    raw = 'SPIX_' + secrets.token_urlsafe(32)
                    expiry = self.parent.clock() + KEY_TTL
                    config = dict(mode='bot', token_hash=digest(raw), expires_at=expiry,
                                  bootstrap_token=raw, bootstrap_until=self.parent.clock() + BOOTSTRAP_TTL,
                                  request_id=request)
                    for provider, row, previous in zip(BOT_PROVIDERS, rows, configs):
                        encrypted = self.parent._encrypt(config)
                        if (previous.get('mode') == 'bot' and row.get('config') and
                                row.get('owner_id') == actor['id'] and row['state'] in ('configured', 'connected')):
                            self.domain.rotate_bridge_config(actor, provider, encrypted, generation=row['generation'])
                        else:
                            self.domain.put_connection(
                                actor, provider, config=encrypted, credential=None, identity=None,
                                expected_generation=row['generation'],
                                request_hash=digest(canonical([request, provider, 'bot'])),
                            )
                        self.domain.remember_bridge_issue(
                            actor, provider, markers[provider],
                            digest(canonical([request, provider, 'bot'])),
                        )
                for provider in BOT_PROVIDERS:
                    row = self.domain.connection(actor, provider)
                    self.jobs.queue(actor, provider, 'catalog', generation=row['generation'])
                self.office.audit(actor, 'integration.bot.key.issued', 'google_calendar+onedrive')
                return {'token': raw, 'expires_at': _iso(expiry), 'providers': list(BOT_PROVIDERS),
                        'instructions': self.instructions()}

    def _configured(self, row):
        config = self._config(row)
        if (config.get('mode') != 'bot' or row['state'] not in ('configured', 'connected') or
                not isinstance(config.get('token_hash'), str)):
            raise Problem(409, 'Den vorhandenen Bot zuerst in Smartplan verbinden.')
        if config.get('expires_at', 0) <= self.parent.clock():
            raise Problem(409, 'Der Botzugang ist abgelaufen. Bitte einen neuen Schlüssel erstellen.')
        return config

    def request_catalogs(self, token, data):
        _object(data, ())
        with self.office.lock, self.office.db:
            actor = self.parent._actor(token, owner=True)
            for provider in BOT_PROVIDERS:
                row = self.domain.connection(actor, provider)
                self._configured(row)
                self.jobs.queue(actor, provider, 'catalog', generation=row['generation'])
        return self.parent.status(token)

    def catalog(self, token, provider, data):
        _object(data, ('query', 'generation'))
        query = _text(data.get('query', ''), 2048, 'Suche', empty=True).casefold()
        with self.office.lock, self.office.db:
            actor = self.parent._actor(token, owner=True)
            row = self.domain.connection(actor, provider)
            self._configured(row)
            if 'generation' in data and _generation(data) != row['generation']:
                raise Problem(409, 'Das verbundene Konto wurde inzwischen geändert.')
            latest = self.jobs.latest(actor, provider, 'catalog', None, generation=row['generation'])
            pending = None
            if latest is None or latest['completed_at'] < self.parent.clock() - FRESH_SECONDS:
                failure = self._task_error(self._latest_task(row, 'catalog'))
                pending = self.jobs.queue(actor, provider, 'catalog', generation=row['generation'])
            else:
                failure = None
            key = 'calendars' if provider == 'google_calendar' else 'folders'
            items = (latest['payload'].get(key, []) if latest else [])
            if query:
                items = [item for item in items if query in
                         (item.get('name', '') + ' ' + item.get('path', '')).casefold()]
            return {'items': items, 'pending': pending is not None,
                    'job_id': pending['id'] if pending else None, 'generation': row['generation'],
                    'synced_at': _iso(latest['completed_at']) if latest else None,
                    'error': failure, 'message': failure}

    @staticmethod
    def _resource(provider, selection):
        return (selection['calendar_id'] if provider == 'google_calendar' else
                canonical({key: selection[key] for key in ('folder_id', 'drive_id')}))

    def _preview_selection(self, provider, data):
        fields = ('calendar_id',) if provider == 'google_calendar' else ('folder_id', 'drive_id')
        _object(data, (*fields, 'generation'), (*fields, 'generation'))
        return {key: _text(data[key], 2048, 'Projektauswahl') for key in fields}

    def _known(self, actor, provider, row, selection):
        catalog = self.jobs.latest(actor, provider, 'catalog', None, generation=row['generation'])
        if not catalog:
            raise Problem(409, 'Zuerst den Kontokatalog vom vorhandenen Bot übernehmen lassen.')
        if provider == 'google_calendar':
            valid = any(item['id'] == selection['calendar_id'] for item in catalog['payload']['calendars'])
        else:
            valid = any(item['id'] == selection['folder_id'] and item['drive_id'] == selection['drive_id']
                        for item in catalog['payload']['folders'])
        if not valid:
            raise Problem(409, 'Die Auswahl ist im bestätigten Kontokatalog nicht enthalten. Bitte aktualisieren.')

    def preview(self, token, project, provider, data):
        selection = self._preview_selection(provider, data)
        generation = _generation(data)
        resource = self._resource(provider, selection)
        with self.office.lock, self.office.db:
            actor = self.parent._actor(token, owner=True)
            self.domain.project(actor, project, provider, write=True)
            row = self.domain.connection(actor, provider)
            self._configured(row)
            if row['generation'] != generation:
                raise Problem(409, 'Das verbundene Konto wurde inzwischen geändert.')
            self._known(actor, provider, row, selection)
            latest = self.jobs.latest(actor, provider, 'resource', resource, generation=generation)
            failure = self._resource_failure(row, resource, latest)
            if latest is not None and not failure and latest['completed_at'] >= self.parent.clock() - FRESH_SECONDS:
                return dict(latest['payload'], generation=generation, pending=False,
                            synced_at=_iso(latest['completed_at']))
            failure = failure or self._task_error(self._latest_task(row, 'resource', resource))
            job = self.jobs.queue(actor, provider, 'resource', generation=generation,
                                  resource=resource, project_id=project, selection=selection)
            return {'pending': True, 'job_id': job['id'], 'generation': generation,
                    'error': failure,
                    'message': ((failure + ' Ein erneuter Abruf wurde angefordert. ') if failure else '') +
                               'Der Bot liefert die Auswahl beim nächsten Fünfminutenlauf. Anschließend erneut laden.'}

    def _normalize(self, provider, kind, payload, selection=None):
        if provider == 'google_calendar':
            from online import integration_google as module
        else:
            from online import integration_onedrive as module
        normalize = getattr(module, 'normalize_bridge_' + kind)
        try:
            return normalize(payload) if kind == 'catalog' else normalize(payload, selection)
        except Problem:
            raise
        except (KeyError, TypeError, ValueError, OverflowError):
            raise Problem(400, 'Die Botdaten entsprechen nicht dem angeforderten Projektumfang.') from None

    def link(self, token, project, provider, data):
        remote, selection = _selection(provider, data)
        revision, generation, request = _revision(data), _generation(data), _request_id(data)
        replay = self.parent.replay_link(
            token, project, provider, remote, selection, generation, revision, request,
        )
        if replay is not None:
            return replay
        resource = self._resource(provider, selection)
        with self.office.lock, self.office.db:
            actor = self.parent._actor(token, owner=True)
            replay = self.parent._replay_link_locked(
                actor, project, provider, remote, selection, generation, revision, request,
            )
            if replay is not None:
                return replay
            self.domain.project(actor, project, provider, write=True)
            row = self.domain.connection(actor, provider)
            self._configured(row)
            if row['generation'] != generation:
                raise Problem(409, 'Das verbundene Konto wurde inzwischen geändert.')
            self._known(actor, provider, row, selection)
            latest = self.jobs.latest(actor, provider, 'resource', resource, generation=generation)
            if latest is None or latest['completed_at'] < self.parent.clock() - FRESH_SECONDS:
                raise Problem(409, 'Die Auswahl zuerst über die Vorschau aktuell vom Bot bestätigen lassen.')
            payload = dict(latest['payload'], complete=True)
            if provider == 'google_calendar':
                selected = set(selection['event_ids'])
                payload['events'] = [event for event in payload['events'] if event['id'] in selected]
            payload = self._normalize(provider, 'snapshot', payload, selection)
            binding = self.domain.bind(
                actor, project, provider, remote, selection, generation=generation,
                revision=revision, request_id=request,
            )
            self.domain.save_snapshot(
                actor, project, provider, payload, generation=generation,
                revision=binding['revision'], synced_at=_iso(latest['completed_at']),
            )
            self.jobs.queue(actor, provider, 'snapshot', generation=generation, resource=resource,
                            project_id=project, revision=binding['revision'], selection=selection)
            return self.parent._project_status(actor, project, provider)

    def sync(self, token, project, provider, data):
        _object(data, ('revision', 'generation'), ('revision', 'generation'))
        revision, generation = _revision(data), _generation(data)
        with self.office.lock, self.office.db:
            actor = self.parent._actor(token)
            row = self.domain.project_connection(actor, project, provider)
            self._configured(row)
            binding = self.domain.binding(actor, project, provider)
            if (row['generation'] != generation or not binding or not binding.get('data') or
                    binding['generation'] != generation or binding['revision'] != revision):
                raise Problem(409, 'Die Projektzuordnung wurde inzwischen geändert.')
            # Queue creation uses the active owner of the provider delegation.
            owner = {'id': row['owner_id']}
            self.jobs.queue(owner, provider, 'snapshot', generation=generation,
                            resource=self._resource(provider, binding['data']), project_id=project,
                            revision=revision, selection=binding['data'])
            return self.parent._project_status(actor, project, provider)

    def _authenticate(self, raw, *, touch):
        if not isinstance(raw, str) or not 8 <= len(raw) <= 200:
            raise Problem(401, 'Geschützter Smartplan-Projektbotzugang erforderlich.')
        checksum = digest(raw)
        result = {}
        with self.office.lock, self.office.db:
            for provider in BOT_PROVIDERS:
                stored = self.office.db.execute(
                    'SELECT owner_id FROM external_connections WHERE provider=?', (provider,),
                ).fetchone()
                if not stored:
                    continue
                actor = self.office.db.execute(
                    "SELECT id,email,role FROM users WHERE id=? AND active=1 AND role='owner'",
                    (stored['owner_id'],),
                ).fetchone()
                if not actor:
                    continue
                actor = dict(actor)
                row = self.domain.connection(actor, provider)
                config = self._config(row)
                expected = config.get('token_hash')
                if (config.get('mode') != 'bot' or not isinstance(expected, str) or
                        not hmac.compare_digest(checksum, expected) or
                        config.get('expires_at', 0) <= self.parent.clock() or
                        row['state'] not in ('configured', 'connected')):
                    continue
                if touch:
                    self.jobs.touch(actor, provider, checksum)
                result[provider] = {'actor': actor, 'row': row}
            if not result:
                raise Problem(401, 'Projektbotzugang fehlt, ist abgelaufen oder wurde widerrufen.')
        return result

    def touch_token(self, raw):
        self._authenticate(raw, touch=True)

    def pending(self, raw):
        authenticated = self._authenticate(raw, touch=True)
        response = []
        with self.office.lock, self.office.db:
            current = self._authenticate(raw, touch=False)
            for provider in authenticated:
                if provider not in current:
                    continue
                scope = current[provider]
                for job in self.jobs.pending(scope['actor'], provider, scope['row']['generation']):
                    response.append({key: job.get(key) for key in (
                        'id', 'provider', 'kind', 'generation', 'requested_generation',
                        'resource', 'selection', 'project_id', 'revision', 'expires_at',
                    )})
        return {'providers': sorted(current), 'jobs': response}

    def _lookup(self, authenticated, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r'[a-f0-9]{32}', job_id):
            raise Problem(404, 'Botauftrag ist nicht verfügbar.')
        for provider, scope in authenticated.items():
            try:
                job = self.jobs.job(scope['actor'], provider, job_id,
                                    generation=scope['row']['generation'])
                return provider, scope, job
            except Problem as error:
                if error.status != 404:
                    raise
        raise Problem(404, 'Botauftrag ist nicht verfügbar.')

    def deliver(self, raw, job_id, data, *, counted=False):
        authenticated = self._authenticate(raw, touch=not counted)
        with self.office.lock, self.office.db:
            provider, scope, job = self._lookup(authenticated, job_id)
        if isinstance(data, dict) and 'error_code' in data:
            _object(data, ('source_id', 'error_code'), ('source_id', 'error_code'))
            error = data['error_code']
            if not isinstance(error, str) or error not in ERROR_CODES:
                raise Problem(400, 'Bekannter sicherer Botfehlercode erwartet.')
            payload = None
        else:
            _object(data, ('source_id', 'complete', 'payload'), ('source_id', 'complete', 'payload'))
            if data['complete'] is not True:
                raise Problem(400, 'Nur vollständig gelesene Botdaten bestätigen.')
            error = None
            payload = self._normalize(provider, job['kind'], data['payload'], job['selection'])
        source = _text(data['source_id'], 200, 'Quellenrevision')
        with self.office.lock, self.office.db:
            authenticated = self._authenticate(raw, touch=False)
            current_provider, scope, fresh = self._lookup(authenticated, job_id)
            if current_provider != provider or fresh['generation'] != job['generation']:
                raise Problem(409, 'Der Botauftrag wurde inzwischen abgelöst.')
            actor, row = scope['actor'], scope['row']
            generation, result_generation = row['generation'], row['generation']
            if fresh['status'] == 'pending' and error is None:
                if fresh['kind'] == 'catalog':
                    identity = payload['identity']
                    if row['state'] == 'connected':
                        if (row.get('identity') or {}).get('id') != identity['id']:
                            raise Problem(409, 'Der Bot meldet ein anderes Anbieterkonto. Die Verbindung zuerst ausdrücklich neu einrichten.')
                    else:
                        row = self.domain.put_connection(
                            actor, provider, credential=self.parent._encrypt({'mode': 'bot', 'account_id': identity['id']}),
                            identity=identity, expected_generation=generation,
                        )
                        result_generation = row['generation']
                elif fresh['kind'] == 'snapshot':
                    self.domain.save_snapshot(
                        actor, fresh['project_id'], provider, payload, generation=generation,
                        revision=fresh['revision'], synced_at=self.parent._now(),
                    )
            receipt = self.jobs.complete(
                actor, provider, job_id, generation=generation, result_generation=result_generation,
                payload=payload, source_id=source, error_code=error,
            )
            if error and fresh['status'] == 'pending' and fresh['kind'] == 'snapshot':
                safe = {'rate_limited': 'rate_limited', 'timeout': 'timeout',
                        'reconnect_required': 'reconnect_required', 'permission_denied': 'reconnect_required',
                        'unsupported': 'invalid_response', 'resource_too_large': 'invalid_response'}.get(
                            error, 'provider_unavailable')
                self.domain.record_error(
                    actor, fresh['project_id'], provider, safe,
                    generation=generation, revision=fresh['revision'],
                )
            if not receipt['duplicate']:
                self.office.audit(actor, 'integration.bot.delivered', job_id)
            return {'status': 'received', 'job_id': job_id, 'idempotent': receipt['duplicate']}

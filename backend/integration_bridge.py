"""Transactional metadata jobs for the existing Google Calendar/OneDrive bot.

The caller authenticates a bot credential and owns Office's lock/transaction.
No credentials, provider IO or original document bytes belong in this module.
"""
import hashlib
import json
import math
import re
import sqlite3
import time
import uuid

from core import Problem, canonical


PROVIDERS = ('google_calendar', 'onedrive')
KINDS = ('catalog', 'resource', 'snapshot')
ERROR_CODES = ('provider_unavailable', 'reconnect_required', 'rate_limited',
               'timeout', 'invalid_response', 'not_found', 'permission_denied',
               'unsupported', 'resource_too_large')
TTL_SECONDS = 3600
MAX_PENDING = 200
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
_ID = re.compile(r'[a-f0-9]{32}\Z')
_HASH = re.compile(r'[a-f0-9]{64}\Z')


def schema_statements():
    return [
        '''CREATE TABLE IF NOT EXISTS external_bridge_jobs(
          id TEXT PRIMARY KEY CHECK(length(id)=32),
          provider TEXT NOT NULL REFERENCES external_connections(provider)
            CHECK(provider IN ('google_calendar','onedrive')),
          owner_id TEXT NOT NULL REFERENCES users(id),
          kind TEXT NOT NULL CHECK(kind IN ('catalog','resource','snapshot')),
          generation INTEGER NOT NULL CHECK(generation>0),
          requested_generation INTEGER NOT NULL CHECK(requested_generation>0),
          resource TEXT CHECK(resource IS NULL OR length(resource)<=2048),
          project_id TEXT REFERENCES projects(id),
          revision INTEGER CHECK(revision IS NULL OR revision>0),
          selection_json TEXT NOT NULL CHECK(length(selection_json)<=65536),
          request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
          status TEXT NOT NULL CHECK(status IN ('pending','completed','failed','expired')),
          payload_json TEXT CHECK(payload_json IS NULL OR length(payload_json)<=2097152),
          payload_sha256 TEXT CHECK(payload_sha256 IS NULL OR length(payload_sha256)=64),
          source_id TEXT CHECK(source_id IS NULL OR length(source_id)<=200),
          error_code TEXT CHECK(error_code IS NULL OR error_code IN
            ('provider_unavailable','reconnect_required','rate_limited','timeout','invalid_response',
             'not_found','permission_denied','unsupported','resource_too_large')),
          created_at DOUBLE PRECISION NOT NULL, expires_at DOUBLE PRECISION NOT NULL,
          completed_at DOUBLE PRECISION,
          CHECK(expires_at>created_at AND expires_at<=created_at+3600),
          CHECK(kind!='snapshot' OR (project_id IS NOT NULL AND revision IS NOT NULL AND resource IS NOT NULL)),
          CHECK(kind!='catalog' OR (project_id IS NULL AND revision IS NULL AND resource IS NULL)))''',
        '''CREATE TABLE IF NOT EXISTS external_bridge_limits(
          provider TEXT NOT NULL REFERENCES external_connections(provider)
            CHECK(provider IN ('google_calendar','onedrive')),
          token_hash TEXT NOT NULL CHECK(length(token_hash)=64),
          window_start DOUBLE PRECISION NOT NULL,
          request_count INTEGER NOT NULL CHECK(request_count>0 AND request_count<=300),
          PRIMARY KEY(provider,token_hash))''',
        'CREATE INDEX IF NOT EXISTS external_bridge_pending ON external_bridge_jobs(provider,generation,status,expires_at)',
        "CREATE UNIQUE INDEX IF NOT EXISTS external_bridge_dedup ON external_bridge_jobs(provider,generation,owner_id,request_hash) WHERE status='pending'",
        'CREATE INDEX IF NOT EXISTS external_bridge_latest ON external_bridge_jobs(provider,generation,kind,resource,status,completed_at)',
    ]


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _integer(value):
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise Problem(400, 'Gültige Integrationsgeneration oder Zuordnungsversion erwartet')
    return value


def _opaque(value, maximum=2048):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or not value.strip() or not value.isprintable():
        raise Problem(400, 'Ungültige externe Kennung')
    return value


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise Problem(400, 'Ungültige Botauftrags-ID')
    return value


def _provider(value):
    if not isinstance(value, str) or value not in PROVIDERS:
        raise Problem(400, 'Unbekannte Botintegration')
    return value


def _json(value, maximum):
    pending, list_items = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        if depth > 20:
            raise Problem(400, 'Botdaten sind zu tief verschachtelt')
        if isinstance(item, dict):
            for key, child in item.items():
                if (not isinstance(key, str) or not key or len(key)>200 or
                        any(ord(char)<32 for char in key) or key.casefold() in
                        {'access_token','refresh_token','client_secret','api_token','authorization','credential','config'}):
                    raise Problem(400, 'Zugangsdaten gehören nicht in Botaufträge')
                pending.append((child, depth + 1))
        elif isinstance(item, list):
            list_items += len(item)
            if list_items > 1000:
                raise Problem(400, 'Zu viele Botdatensätze')
            pending.extend((child, depth + 1) for child in item)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise Problem(400, 'Gültige JSON-Botdaten erwartet')
    try:
        result = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(result.encode('utf-8')) > maximum:
            raise Problem(413, 'Botdaten sind zu groß')
        return result
    except (ValueError, TypeError, UnicodeError):
        raise Problem(400, 'Gültige JSON-Botdaten erwartet') from None


def _resource(provider, value):
    value = _opaque(value)
    if provider == 'onedrive':
        try:
            parsed = json.loads(value)
        except (ValueError, RecursionError):
            raise Problem(400, 'OneDrive-Ordner und Laufwerk erwartet') from None
        if not isinstance(parsed, dict) or set(parsed) != {'folder_id', 'drive_id'}:
            raise Problem(400, 'OneDrive-Ordner und Laufwerk erwartet')
        value = _json({key: _opaque(parsed[key]) for key in ('folder_id', 'drive_id')}, 2048)
    return value


def _selection(provider, resource, selection, snapshot):
    selection = {} if selection is None else selection
    if not isinstance(selection, dict):
        raise Problem(400, 'Ausdrückliche Botdatenauswahl erwartet')
    if snapshot:
        if provider == 'google_calendar':
            if (set(selection) != {'calendar_id', 'event_ids'} or selection['calendar_id'] != resource or
                    not isinstance(selection['event_ids'], list) or len(selection['event_ids']) > 50):
                raise Problem(400, 'Ausgewählten Kalender und höchstens 50 Termine erwartet')
            values = [_opaque(item) for item in selection['event_ids']]
            if len(set(values)) != len(values):
                raise Problem(400, 'Terminkennungen müssen eindeutig sein')
            selection = dict(calendar_id=resource, event_ids=sorted(values))
        elif (set(selection) != {'folder_id','drive_id'} or
              _resource(provider, _json(selection, 2048)) != resource):
            raise Problem(400, 'Ausgewählten OneDrive-Ordner mit Laufwerk erwartet')
    return _json(selection, 65536)


def _fingerprint(row):
    return _digest(canonical({key: row[key] for key in
        ('provider','kind','requested_generation','resource','project_id','revision','selection_json')}))


class IntegrationBridgeJobs:
    def __init__(self, office, clock=time.time):
        self.office, self.db, self.clock = office, office.db, clock
        if isinstance(self.db, sqlite3.Connection) and not self.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='external_bridge_jobs'").fetchone():
            if self.db.in_transaction:
                raise RuntimeError('Initialize bridge schema before the caller transaction.')
            with office.lock, self.db:
                for statement in schema_statements():
                    self.db.execute(statement)

    def _now(self):
        result = self.clock()
        if type(result) not in (int, float) or not math.isfinite(result) or not 0<=result<=32503680000:
            raise Problem(409, 'Ungültige Systemzeit für Botaufträge')
        return float(result)

    def _connection(self, actor, provider, generation=None):
        provider = _provider(provider)
        if not isinstance(actor, dict) or not isinstance(actor.get('id'), str):
            raise Problem(401, 'Bitte anmelden')
        fresh = self.db.execute('SELECT id,role,active FROM users WHERE id=?', (actor['id'],)).fetchone()
        if not fresh or fresh['active'] != 1:
            raise Problem(401, 'Bitte anmelden')
        self.office.require(dict(fresh), ('owner',))
        connection = self.db.execute('SELECT * FROM external_connections WHERE provider=?', (provider,)).fetchone()
        if not connection or connection['state'] not in ('configured','connected'):
            raise Problem(409, 'Die Botintegration muss erneut verbunden werden')
        owner = self.db.execute('SELECT role,active FROM users WHERE id=?', (connection['owner_id'],)).fetchone()
        if not owner or owner['role'] != 'owner' or owner['active'] != 1:
            raise Problem(409, 'Die Botintegration muss erneut verbunden werden')
        if generation is not None and _integer(generation) != connection['generation']:
            raise Problem(409, 'Die Botintegration wurde inzwischen geändert')
        return dict(connection), dict(fresh)

    def _project(self, actor, row, connection):
        if row['owner_id'] != connection['owner_id']:
            raise Problem(409, 'Der Verantwortliche der Botintegration wurde geändert')
        if row['project_id'] is not None:
            self.office.project(actor, row['project_id'])
        if row['kind'] != 'snapshot':
            return
        link = self.db.execute('SELECT * FROM external_project_links WHERE project_id=? AND provider=?',
                               (row['project_id'], row['provider'])).fetchone()
        try:
            remote = json.loads(row['resource'])['folder_id'] if row['provider']=='onedrive' else row['resource']
        except (ValueError,TypeError,KeyError):
            raise Problem(409, 'Die Projektzuordnung des Botauftrags wurde geändert') from None
        if (connection['state'] != 'connected' or not link or link['active'] != 1 or
                link['generation'] != row['generation'] or link['revision'] != row['revision'] or
                link['remote'] != remote):
            raise Problem(409, 'Die Projektzuordnung des Botauftrags wurde geändert')
        try:
            matches = _selection(row['provider'], row['resource'], json.loads(link['selection_json']), True)==row['selection_json']
        except (Problem,ValueError,TypeError):
            matches = False
        if not matches:
            raise Problem(409, 'Die Projektzuordnung des Botauftrags wurde geändert')

    @staticmethod
    def _view(row, *, duplicate=False):
        result = dict(row)
        if (_fingerprint(result)!=result['request_hash'] or
                result['payload_json'] is not None and _digest(result['payload_json'])!=result['payload_sha256']):
            raise Problem(409, 'Der gespeicherte Botauftrag ist beschädigt')
        result['job_id'] = result['id']
        try:
            result['selection'] = json.loads(result['selection_json'])
            result['payload'] = json.loads(result['payload_json']) if result['payload_json'] is not None else None
        except (ValueError,TypeError,RecursionError):
            raise Problem(409, 'Der gespeicherte Botauftrag ist beschädigt') from None
        result['duplicate'] = duplicate
        return result

    def _expire(self, provider, now):
        self.db.execute("UPDATE external_bridge_jobs SET status='expired' WHERE provider=? AND status='pending' AND "
            "(expires_at<=? OR generation!=(SELECT generation FROM external_connections WHERE provider=?) "
            "OR owner_id!=(SELECT owner_id FROM external_connections WHERE provider=?))", (provider,now,provider,provider))
        self.db.execute("UPDATE external_bridge_jobs SET status='expired' WHERE provider=? AND status='pending' "
            "AND kind='snapshot' AND NOT EXISTS(SELECT 1 FROM external_project_links l "
            "WHERE l.project_id=external_bridge_jobs.project_id AND l.provider=external_bridge_jobs.provider "
            "AND l.active=1 AND l.generation=external_bridge_jobs.generation AND l.revision=external_bridge_jobs.revision "
            "AND l.selection_json=external_bridge_jobs.selection_json)", (provider,))

    def queue(self, actor, provider, kind, *, generation, resource=None, project_id=None, revision=None, selection=None):
        connection, actor = self._connection(actor, provider, generation)
        if kind not in KINDS:
            raise Problem(400, 'Ungültige Botauftragsart')
        if kind == 'catalog':
            if resource is not None or project_id is not None or revision is not None or selection not in (None, {}):
                raise Problem(400, 'Katalogaufträge haben keine Projektzuordnung')
        else:
            resource = _resource(provider, resource)
            if connection['state'] != 'connected':
                raise Problem(409, 'Zuerst das Botkonto durch einen Katalogabruf bestätigen')
        project_id = _identifier(project_id) if project_id is not None else None
        revision = _integer(revision) if revision is not None else None
        if kind == 'snapshot' and (project_id is None or revision is None):
            raise Problem(400, 'Projekt und Zuordnungsversion für Botabgleich erwartet')
        selection_json = _selection(provider, resource, selection, kind == 'snapshot')
        now = self._now()
        row = dict(id=uuid.uuid4().hex, provider=provider, owner_id=connection['owner_id'], kind=kind,
            generation=generation, requested_generation=generation, resource=resource, project_id=project_id,
            revision=revision, selection_json=selection_json, status='pending', payload_json=None,
            payload_sha256=None, source_id=None, error_code=None, created_at=now,
            expires_at=now+TTL_SECONDS, completed_at=None)
        row['request_hash'] = _fingerprint(row)
        self._project(actor, row, connection)
        self._expire(provider, now)
        previous = self.db.execute("SELECT * FROM external_bridge_jobs WHERE provider=? AND generation=? AND owner_id=? "
            "AND request_hash=? AND status='pending' AND expires_at>? ORDER BY created_at,id LIMIT 1",
            (provider,generation,connection['owner_id'],row['request_hash'],now)).fetchone()
        if previous:
            return self._view(previous, duplicate=True)
        count = self.db.execute("SELECT COUNT(*) FROM external_bridge_jobs WHERE provider=? AND status='pending' AND expires_at>?", (provider,now)).fetchone()[0]
        if count >= MAX_PENDING:
            raise Problem(429, 'Zu viele offene Botaufträge')
        keys = tuple(row)
        self.db.execute('INSERT INTO external_bridge_jobs('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')', tuple(row[key] for key in keys))
        return self._view(row)

    def pending(self, actor, provider, generation):
        connection, actor = self._connection(actor, provider, generation)
        now = self._now()
        self._expire(provider, now)
        rows = self.db.execute("SELECT * FROM external_bridge_jobs WHERE provider=? AND generation=? AND owner_id=? "
            "AND status='pending' AND expires_at>? ORDER BY created_at,id LIMIT 200", (provider,generation,connection['owner_id'],now)).fetchall()
        result = []
        for row in rows:
            try:
                self._project(actor, row, connection)
            except Problem as error:
                if error.status in (404,409):
                    continue
                raise
            result.append(self._view(row))
            if len(result) == 50:
                break
        return result

    def job(self, actor, provider, job_id, *, generation):
        connection, actor = self._connection(actor, provider, generation)
        row = self.db.execute('SELECT * FROM external_bridge_jobs WHERE id=? AND provider=? AND generation=? AND owner_id=?',
                             (_identifier(job_id),provider,generation,connection['owner_id'])).fetchone()
        if not row:
            raise Problem(404, 'Botauftrag nicht verfügbar')
        self._project(actor,row,connection)
        if row['status'] == 'expired' or (row['status']=='pending' and row['expires_at']<=self._now()):
            raise Problem(409, 'Der Botauftrag ist abgelaufen')
        return self._view(row)

    def latest(self, actor, provider, kind, resource, *, generation):
        connection, actor = self._connection(actor, provider, generation)
        if kind not in KINDS:
            raise Problem(400, 'Ungültige Botauftragsart')
        resource = None if kind == 'catalog' and resource is None else _resource(provider,resource)
        comparison = 'resource IS NULL' if resource is None else 'resource=?'
        parameters = (provider,generation,connection['owner_id'],kind) + (() if resource is None else (resource,))
        order = 'created_at DESC,completed_at DESC,id DESC' if kind in ('catalog','resource') else 'completed_at DESC,id DESC'
        rows = self.db.execute("SELECT * FROM external_bridge_jobs WHERE provider=? AND generation=? AND owner_id=? AND kind=? "
            "AND status='completed' AND "+comparison+' ORDER BY '+order+' LIMIT 200', parameters).fetchall()
        for row in rows:
            try:
                self._project(actor,row,connection)
            except Problem as error:
                if error.status in (404,409):
                    continue
                raise
            return self._view(row)
        return None

    def complete(self, actor, provider, job_id, *, generation, payload, source_id,
                 error_code=None, result_generation=None):
        generation = _integer(generation)
        target = generation if result_generation is None else _integer(result_generation)
        connection, actor = self._connection(actor, provider, target)
        row = self.db.execute('SELECT * FROM external_bridge_jobs WHERE id=? AND provider=? AND owner_id=?',
                             (_identifier(job_id),provider,connection['owner_id'])).fetchone()
        if not row:
            raise Problem(404, 'Botauftrag nicht verfügbar')
        row = dict(row)
        if target != generation:
            if (target != generation+1 or row['kind']!='catalog' or row['requested_generation']!=generation or
                    row['generation'] not in (generation,target) or error_code is not None):
                raise Problem(409, 'Die Generation dieses Botauftrags darf nicht übernommen werden')
        elif row['generation'] != generation:
            raise Problem(409, 'Die Botintegration wurde inzwischen geändert')
        if row['status']=='pending' and row['generation']!=generation:
            raise Problem(409, 'Die Botintegration wurde inzwischen geändert')
        self._project(actor,row,connection)
        source_id = _opaque(source_id,200)
        if error_code is not None and error_code not in ERROR_CODES:
            raise Problem(400, 'Sicherer Botfehlercode erwartet')
        encoded = _json(payload, MAX_PAYLOAD_BYTES)
        checksum = _digest(encoded)
        if row['status'] in ('completed','failed'):
            if row['payload_sha256']!=checksum or row['source_id']!=source_id or row['error_code']!=error_code:
                raise Problem(409, 'Dieser Botauftrag wurde bereits mit einem anderen Ergebnis bestätigt')
            return self._view(row,duplicate=True)
        now = self._now()
        if now<row['created_at']:
            raise Problem(409, 'Die Systemzeit liegt vor der Erstellung des Botauftrags')
        if row['status']!='pending' or row['expires_at']<=now:
            raise Problem(409, 'Der Botauftrag ist abgelaufen')
        status = 'failed' if error_code else 'completed'
        self.db.execute('UPDATE external_bridge_jobs SET generation=?,status=?,payload_json=?,payload_sha256=?,source_id=?,error_code=?,completed_at=? WHERE id=?',
            (target,status,encoded,checksum,source_id,error_code,now,row['id']))
        row.update(generation=target,status=status,payload_json=encoded,payload_sha256=checksum,
                   source_id=source_id,error_code=error_code,completed_at=now)
        return self._view(row)

    def touch(self, actor, provider, token_hash):
        self._connection(actor,provider)
        if not isinstance(token_hash,str) or not _HASH.fullmatch(token_hash):
            raise Problem(400, 'Ungültige Botzugangsprüfsumme')
        now = self._now()
        row = self.db.execute('SELECT * FROM external_bridge_limits WHERE provider=? AND token_hash=?', (provider,token_hash)).fetchone()
        count = row['request_count'] if row and now < row['window_start']+60 else 0
        if count >= 300:
            raise Problem(429, 'Zu viele Botabrufe; bitte später erneut versuchen')
        start = row['window_start'] if count else now
        self.db.execute('INSERT INTO external_bridge_limits(provider,token_hash,window_start,request_count) VALUES(?,?,?,?) '
            'ON CONFLICT(provider,token_hash) DO UPDATE SET window_start=excluded.window_start,request_count=excluded.request_count',
            (provider,token_hash,start,count+1))
        return {'remaining':299-count,'window_start':start}


def sanitize_after_restore(office):
    office.db.execute('DELETE FROM external_bridge_limits')
    office.db.execute('DELETE FROM external_bridge_jobs')


def validate_integrity(office):
    """Validate history structurally; old epochs are retained but never exposed."""
    pending_counts, pending_hashes = {}, set()
    for raw in office.db.execute('SELECT * FROM external_bridge_jobs').fetchall():
        row = dict(raw)
        try:
            _identifier(row['id'])
            _provider(row['provider'])
            if row['kind'] not in KINDS or row['status'] not in ('pending','completed','failed','expired'):
                raise ValueError('invalid state')
            _integer(row['generation']); _integer(row['requested_generation'])
            if row['generation']!=row['requested_generation'] and not (row['kind']=='catalog' and row['generation']==row['requested_generation']+1 and row['status']=='completed'):
                raise ValueError('invalid generation')
            if row['resource'] is not None and _resource(row['provider'],row['resource'])!=row['resource']:
                raise ValueError('invalid resource')
            if row['kind']=='resource' and row['resource'] is None:
                raise ValueError('missing resource')
            if row['revision'] is not None:
                _integer(row['revision'])
            if row['project_id'] is not None:
                _identifier(row['project_id'])
            selection = _selection(row['provider'],row['resource'],json.loads(row['selection_json']),row['kind']=='snapshot')
            if selection!=row['selection_json'] or _fingerprint(row)!=row['request_hash']:
                raise ValueError('invalid request hash')
            if row['kind']=='catalog' and any(row[key] is not None for key in ('resource','project_id','revision')):
                raise ValueError('invalid catalog')
            if row['kind']=='catalog' and row['selection_json']!='{}':
                raise ValueError('invalid catalog selection')
            if row['kind']=='snapshot' and any(row[key] is None for key in ('resource','project_id','revision')):
                raise ValueError('invalid snapshot')
            times = [row['created_at'],row['expires_at']]+([] if row['completed_at'] is None else [row['completed_at']])
            if any(type(value) not in (float,int) or not math.isfinite(value) or value<0 for value in times) or not 0<row['expires_at']-row['created_at']<=TTL_SECONDS:
                raise ValueError('invalid timestamp')
            if row['status'] in ('pending','expired'):
                if any(row[key] is not None for key in ('payload_json','payload_sha256','source_id','error_code','completed_at')):
                    raise ValueError('unfinished receipt')
                if row['status']=='pending':
                    pending_counts[row['provider']] = pending_counts.get(row['provider'],0)+1
                    request = (row['provider'],row['generation'],row['owner_id'],row['request_hash'])
                    if request in pending_hashes or pending_counts[row['provider']]>MAX_PENDING:
                        raise ValueError('invalid pending queue bounds')
                    pending_hashes.add(request)
            else:
                encoded = _json(json.loads(row['payload_json']),MAX_PAYLOAD_BYTES)
                if encoded!=row['payload_json'] or _digest(encoded)!=row['payload_sha256']:
                    raise ValueError('invalid payload hash')
                _opaque(row['source_id'],200)
                if row['completed_at'] is None or not row['created_at']<=row['completed_at']<row['expires_at']:
                    raise ValueError('invalid completion time')
                if ((row['status']=='failed' and row['error_code'] not in ERROR_CODES) or
                        (row['status']=='completed' and row['error_code'] is not None)):
                    raise ValueError('invalid error receipt')
            connection = office.db.execute('SELECT generation FROM external_connections WHERE provider=?',(row['provider'],)).fetchone()
            if not connection or row['generation']>connection['generation'] or not office.db.execute('SELECT 1 FROM users WHERE id=?',(row['owner_id'],)).fetchone():
                raise ValueError('invalid connection reference')
            if row['project_id'] is not None and not office.db.execute('SELECT 1 FROM projects WHERE id=?',(row['project_id'],)).fetchone():
                raise ValueError('invalid project reference')
            if row['kind']=='snapshot':
                link = office.db.execute('SELECT * FROM external_project_links WHERE project_id=? AND provider=?',
                                         (row['project_id'],row['provider'])).fetchone()
                if not link or row['generation']>link['generation'] or row['revision']>link['revision']:
                    raise ValueError('invalid project epoch')
                if (row['generation']==link['generation'] and row['revision']==link['revision'] and
                        (not link['active'] or _selection(row['provider'],row['resource'],json.loads(link['selection_json']),True)!=row['selection_json'])):
                    raise ValueError('invalid current project selection')
        except (Problem, ValueError, TypeError, KeyError, RecursionError) as error:
            raise ValueError('Invalid external bridge job integrity') from error
    for row in office.db.execute('SELECT * FROM external_bridge_limits').fetchall():
        if (row['provider'] not in PROVIDERS or not isinstance(row['token_hash'],str) or not _HASH.fullmatch(row['token_hash']) or
                type(row['request_count']) is not int or not 1<=row['request_count']<=300 or
                type(row['window_start']) not in (float,int) or not math.isfinite(row['window_start']) or row['window_start']<0 or
                not office.db.execute('SELECT 1 FROM external_connections WHERE provider=?',(row['provider'],)).fetchone()):
            raise ValueError('Invalid external bridge rate limit integrity')

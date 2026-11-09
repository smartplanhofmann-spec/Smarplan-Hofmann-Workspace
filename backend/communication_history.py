"""Read-only CRM projection of canonical, freshly authorized source records.

No new message store, implicit email/name matching, provider IO or write path.
Pagination binds a complete filtered visible snapshot; source/rights changes
cannot silently splice two different histories together.
"""
import base64
from datetime import date, datetime, timezone
import hashlib
import json
import re

from core import Problem, canonical
from business_foundation import BusinessFoundation, require_permission
from business_operations import identifier, iso_date, text, transaction

KINDS = ('inquiry', 'sales', 'service', 'document', 'delivery', 'project_note')
MAX_ENTRIES = 2000
MAX_TEXT_BYTES = 8_000_000
ACTIVITIES = dict(note='Notiz', call='Telefonat', email='E-Mail protokolliert', meeting='Besprechung')
DELIVERIES = dict(pending='Versand vorbereitet', sending='Versand läuft',
    accepted='Vom Versandserver angenommen', failed='Versand fehlgeschlagen',
    unknown='Versandergebnis ungeklärt', not_sent='Nicht versendet bestätigt')


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _stamp(value):
    try:
        if not isinstance(value, str):
            raise ValueError()
        if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError()
            return value, 'day'
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat(timespec='seconds'), 'second'
    except (TypeError, ValueError):
        raise Problem(500, 'Der Ursprungsverlauf enthält keinen eindeutigen Zeitpunkt.') from None


def _order(entry):
    value = entry['occurred_at']
    return (value + 'T00:00:00+00:00' if entry['precision'] == 'day' else value, entry['key'])


def _cursor(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,1400}', value):
        raise Problem(400, 'Ungültige Fortsetzung des Kommunikationsverlaufs.')
    try:
        result = json.loads(base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)))
        if (not isinstance(result, dict) or set(result) != {'scope', 'snapshot', 'after'}
                or any(not isinstance(result[k], str) or not re.fullmatch(r'[a-f0-9]{64}', result[k]) for k in ('scope', 'snapshot'))
                or not isinstance(result['after'], list) or len(result['after']) != 2
                or any(not isinstance(v, str) or len(v) > 160 for v in result['after'])):
            raise ValueError()
        return result
    except (ValueError, TypeError, UnicodeError):
        raise Problem(400, 'Ungültige Fortsetzung des Kommunikationsverlaufs.') from None


class CommunicationHistory:
    def __init__(self, office):
        self.office, self.db = office, office.db
        self.foundation = BusinessFoundation(office)

    def listing(self, actor, query):
        allowed = {'customer_id', 'project_id', 'kind', 'q', 'from', 'to', 'limit', 'cursor'}
        if not isinstance(query, dict) or set(query) - allowed:
            raise Problem(400, 'Unbekannte Filter im Kommunikationsverlauf.')
        customer_id = identifier(query['customer_id']) if 'customer_id' in query else None
        project_id = identifier(query['project_id']) if 'project_id' in query else None
        if not customer_id and not project_id:
            raise Problem(400, 'Einen Kunden oder ein Projekt ausdrücklich auswählen.')
        kind = query.get('kind')
        if kind is not None and (not isinstance(kind, str) or kind not in KINDS):
            raise Problem(400, 'Unbekannte Verlaufsquelle.')
        if isinstance(query.get('q'), str) and any(ord(c) < 32 or ord(c) == 127 for c in query['q']):
            raise Problem(400, 'Suchtext ohne Steuerzeichen angeben.')
        q = text(query.get('q', ''), 'Suche', 200)
        start = iso_date(query['from']) if 'from' in query else None
        end = iso_date(query['to']) if 'to' in query else None
        if start and end and start > end:
            raise Problem(400, 'Der Beginn liegt nach dem Ende des Zeitraums.')
        limit = query.get('limit', '50')
        if not isinstance(limit, str) or not re.fullmatch(r'[1-9][0-9]{0,2}', limit) or int(limit) > 100:
            raise Problem(400, 'Zwischen einem und hundert Einträgen pro Seite auswählen.')
        cursor = _cursor(query['cursor']) if 'cursor' in query else None
        with transaction(self.office):
            actor = require_permission(self.office, actor, 'contacts.read', project_id)
            project = dict(self.office.project(actor, project_id)) if project_id else None
            if project:
                if customer_id and project['customer_id'] != customer_id:
                    raise Problem(404, 'Kunde und Projekt sind nicht gemeinsam verfügbar.')
                customer_id = project['customer_id']
            customer = self.foundation.contact(actor, customer_id) if customer_id else None
            if customer and customer['erased_at']:
                raise Problem(404, 'Kontakt nicht verfügbar.')
            scope = dict(customer_id=customer_id, project_id=project_id, kind=kind, q=q,
                         **{'from': start, 'to': end})
            entries = []
            text_bytes = 0

            def emit(category, source_id, revision, *, title, body, occurred_at, recorded_at,
                     status, source, project_ids=(), supersedes=None, superseded=False,
                     provenance='canonical_record', accepted=False):
                nonlocal text_bytes
                if kind is not None and kind != category:
                    return
                for pid in project_ids:
                    if self._permitted(lambda: require_permission(self.office, actor, 'contacts.read', pid)) is None:
                        return
                occurred, precision = _stamp(occurred_at)
                recorded, recorded_precision = _stamp(recorded_at)
                if recorded_precision != 'second':
                    raise Problem(500, 'Der Erfassungszeitpunkt ist nicht eindeutig.')
                if start and occurred[:10] < start or end and occurred[:10] > end:
                    return
                if q and q.casefold() not in (title + ' ' + body).casefold():
                    return
                if len(entries) >= MAX_ENTRIES:
                    raise Problem(413, 'Zu viele sichtbare Einträge. Quelle, Zeitraum oder Projekt enger auswählen.')
                text_bytes += len(title.encode()) + len(body.encode())
                if text_bytes > MAX_TEXT_BYTES:
                    raise Problem(413, 'Zu viel sichtbarer Verlaufstext. Quelle, Zeitraum oder Projekt enger auswählen.')
                key = category + ':' + provenance + ':' + source_id + ':' + str(revision)
                entries.append(dict(key=key, kind=category, source_id=source_id,
                    source_revision=revision, source_sha256=sha(source),
                    project_ids=sorted(set(project_ids)), title=title[:500], text=body[:40000],
                    occurred_at=occurred, precision=precision, recorded_at=recorded,
                    status=status, provenance=provenance, supersedes_key=supersedes,
                    superseded=superseded, accepted_by_server=accepted,
                    recipient_delivery_confirmed=False))

            readable = self._readable()
            inquiry_ids = set()
            if customer_id and 'business_sales' in readable and kind in (None, 'sales', 'inquiry'):
                self._sales(actor, customer_id, project_id, inquiry_ids, emit)
            if customer_id and 'business_service' in readable and kind in (None, 'service', 'inquiry'):
                self._service(actor, customer_id, project_id, inquiry_ids, emit)
            if customer_id and kind in (None, 'inquiry'):
                self._inquiries(actor, customer_id, project_id, inquiry_ids, emit)
            if 'business_documents' in readable and kind in (None, 'document', 'delivery'):
                self._documents(actor, customer_id, project_id, emit)
            if kind in (None, 'project_note'):
                self._notes(actor, customer_id, project_id, emit)

            entries.sort(key=_order, reverse=True)
            scope_hash = sha(scope)
            snapshot = sha(dict(scope=scope, entries=entries))
            offset = 0
            if cursor:
                if cursor['scope'] != scope_hash or cursor['snapshot'] != snapshot:
                    raise Problem(409, 'Verlauf oder Zugriffsrechte wurden geändert. Den Verlauf erneut laden.')
                positions = [i for i, entry in enumerate(entries) if list(_order(entry)) == cursor['after']]
                if len(positions) != 1:
                    raise Problem(400, 'Die Fortsetzung gehört nicht zu diesem Verlauf.')
                offset = positions[0] + 1
            page = entries[offset:offset + int(limit)]
            more = offset + len(page) < len(entries)
            next_cursor = None
            if more:
                data = dict(scope=scope_hash, snapshot=snapshot, after=list(_order(page[-1])))
                next_cursor = base64.urlsafe_b64encode(canonical(data).encode()).decode().rstrip('=')
            return dict(schema_version=1, scope=scope, snapshot_sha256=snapshot,
                customer=None if not customer else dict(id=customer['id'], name=customer['name']),
                project=None if not project else dict(id=project['id'], name=project['name']),
                items=page, next_cursor=next_cursor, has_more=more, page_size=int(limit),
                limitations=[
                    'Nur ausdrücklich verknüpfte und aktuell freigegebene Ursprünge sind enthalten; gleiche Namen oder E-Mail-Adressen erzeugen keine Zuordnung.',
                    'Protokollierte Telefonate, E-Mails und Besprechungen sind manuelle Nachweise. Versandannahme bestätigt weder Zustellung noch Lesen.',
                    'Taggenaue Aktivitäten besitzen keine belegte Uhrzeit. Geschützte Personal- und Finanznotizen aus dem Projektlogbuch sind hier nicht enthalten.',
                ])

    def _readable(self):
        from business_schema import state
        return set(state(self.office)['read_capabilities'])

    def _permitted(self, call):
        try:
            return call()
        except Problem as error:
            if error.status in (403, 404):
                return None
            raise

    def _sales(self, actor, customer_id, project_id, inquiry_ids, emit):
        from business_sales import Sales
        api = Sales(self.office)
        for header in self.db.execute('SELECT * FROM business_sales_opportunities WHERE customer_id=? ORDER BY id', (customer_id,)):
            item = self._permitted(lambda: api.view(actor, header['id']))
            if item is None:
                continue
            projects = sorted({link['project_id'] for link in item['links']})
            if project_id and project_id not in projects:
                continue
            if item['inquiry_id']:
                inquiry_ids.add(item['inquiry_id'])
            for version in api.history(actor, header['id'])['items']:
                emit('sales', header['id'], version['revision'], title=version['title'],
                    body=version['description'], occurred_at=version['created_at'],
                    recorded_at=version['created_at'], status=version['stage'],
                    source=version, project_ids=projects)
            events = api.activities(actor, header['id'])['items']
            superseded = {event['supersedes_id'] for event in events if event['supersedes_id']}
            for event in events:
                emit('sales', event['id'], 1, title=ACTIVITIES[event['kind']] + ' · ' + item['title'],
                    body=event['text'], occurred_at=event['occurred_on'], recorded_at=event['created_at'],
                    status='recorded_activity', source=event, project_ids=projects,
                    superseded=event['id'] in superseded,
                    supersedes='sales:manual_activity:' + event['supersedes_id'] + ':1' if event['supersedes_id'] else None,
                    provenance='manual_activity')

    def _service(self, actor, customer_id, project_id, inquiry_ids, emit):
        from business_service import Service
        api = Service(self.office)
        for header in self.db.execute('SELECT id FROM business_service_cases WHERE customer_id=? ORDER BY id', (customer_id,)):
            item = self._permitted(lambda: api.view(actor, header['id']))
            if item is None or project_id and item['project_id'] != project_id:
                continue
            projects = [item['project_id']] if item['project_id'] else []
            if item['inquiry_id']:
                inquiry_ids.add(item['inquiry_id'])
            history = api.history(actor, item['id'])
            for version in history['versions']:
                emit('service', item['id'], version['revision'], title=version['title'],
                    body=version['description'], occurred_at=version['updated_at'],
                    recorded_at=version['updated_at'], status=version['status'],
                    source=version, project_ids=projects)
            superseded = {e['supersedes_id'] for e in history['events'] if e['supersedes_id']}
            for event in history['events']:
                if event['kind'] not in ACTIVITIES:
                    continue
                values = event['values']
                emit('service', event['id'], 1, title=ACTIVITIES[event['kind']] + ' · ' + item['title'],
                    body=values['text'], occurred_at=values['occurred_on'], recorded_at=event['created_at'],
                    status='recorded_activity', source=event, project_ids=projects,
                    superseded=event['id'] in superseded,
                    supersedes='service:manual_activity:' + event['supersedes_id'] + ':1' if event['supersedes_id'] else None,
                    provenance='manual_activity')

    def _inquiries(self, actor, customer_id, project_id, inquiry_ids, emit):
        from inquiries import Inquiries
        api = Inquiries(self.office)
        if self._permitted(lambda: (api._authorize(actor), True)[1]) is None:
            return
        for row in self.db.execute('SELECT id,customer_id,project_id FROM inquiries ORDER BY id'):
            if row['customer_id'] != customer_id and row['id'] not in inquiry_ids:
                continue
            if project_id and row['project_id'] != project_id and row['id'] not in inquiry_ids:
                continue
            item = api.get(actor, row['id'])
            projects = [item['project_id']] if item['project_id'] else ([project_id] if project_id else [])
            emit('inquiry', item['id'], item['revision'], title=item['subject'], body=item['message'],
                occurred_at=item['received_at'], recorded_at=item['created_at'], status=item['status'],
                source={k:v for k,v in item.items() if k not in ('candidate_customers',)},
                project_ids=projects, provenance='received_inquiry' if item['source']=='gmail' or item['provenance'].get('format')=='eml' else 'recorded_inquiry')

    def _documents(self, actor, customer_id, project_id, emit):
        from business_documents import Documents, LABELS
        api = Documents(self.office)
        for row in self.db.execute('SELECT * FROM business_documents ORDER BY id'):
            if project_id and row['project_id'] != project_id or not project_id and row['customer_id'] != customer_id:
                continue
            if self._permitted(lambda: require_permission(self.office, actor, 'contacts.read', row['project_id'])) is None:
                continue
            item = self._permitted(lambda: api.get(actor, row['id']))
            if item is None:
                continue
            if hashlib.sha256(row['payload_json'].encode()).hexdigest() != row['payload_sha256']:
                raise Problem(500, 'Der Belegnachweis ist beschädigt.')
            title = LABELS[item['kind']] + (' ' + item['number'] if item['number'] else ' · Entwurf')
            emit('document', item['id'], item['revision'], title=title, body=item['title'],
                occurred_at=item['updated_at'], recorded_at=item['updated_at'], status=item['status'],
                source=item, project_ids=[item['project_id']], provenance='current_document_revision')
            for mail in self.db.execute('SELECT * FROM business_document_outbox WHERE document_id=? ORDER BY id', (item['id'],)):
                content = json.loads(mail['payload_json'])
                digest = content.pop('preview_sha256', None)
                if digest != mail['payload_sha256'] or sha(content) != digest:
                    raise Problem(500, 'Der Versandnachweis ist beschädigt.')
                source = dict(content, operation_id=mail['operation_id'], created_at=mail['created_at'])
                emit('delivery', mail['id'], 0, title='Versand vorbereitet · ' + title,
                    body=content['subject'], occurred_at=mail['created_at'], recorded_at=mail['created_at'],
                    status='pending', source=source, project_ids=[item['project_id']], provenance='mail_outbox')
                previous = 'pending'
                transitions = {'pending':{'sending'},'sending':{'accepted','failed','unknown'},'unknown':{'accepted','not_sent'},'failed':{'accepted','not_sent'},'not_sent':{'sending','accepted','unknown'},'accepted':{'accepted','unknown'}}
                receipts = self.db.execute('SELECT * FROM business_document_mail_receipts WHERE outbox_id=? ORDER BY ordinal', (mail['id'],)).fetchall()
                for ordinal, receipt in enumerate(receipts, 1):
                    restored = receipt['status']=='unknown' and receipt['error_code']=='disaster_restore_delivery_unconfirmed' and previous not in ('accepted','unknown')
                    if receipt['operation_id'] != mail['operation_id'] or receipt['ordinal'] != ordinal or receipt['status'] not in DELIVERIES or not restored and receipt['status'] not in transitions[previous]:
                        raise Problem(500, 'Der Versandverlauf ist beschädigt.')
                    previous = receipt['status']
                    emit('delivery', mail['id'], receipt['ordinal'], title=DELIVERIES[receipt['status']] + ' · ' + title,
                        body=content['subject'], occurred_at=receipt['at'], recorded_at=receipt['at'],
                        status=receipt['status'], source=dict(receipt), project_ids=[item['project_id']],
                        provenance='mail_receipt', accepted=receipt['status']=='accepted')

    def _notes(self, actor, customer_id, project_id, emit):
        candidates = ([dict(id=project_id)] if project_id else
                      self.db.execute('SELECT id FROM projects WHERE customer_id=? ORDER BY id', (customer_id,)))
        for project in candidates:
            pid = project['id']
            if self._permitted(lambda: self.foundation.authorize(actor, 'documents.read', pid)) is None:
                continue
            for row in self.db.execute("SELECT * FROM business_feed WHERE project_id=? AND event_type='message' AND visibility='operational' ORDER BY id", (pid,)):
                emit('project_note', row['id'], 1, title='Projektnotiz', body=row['summary'],
                    occurred_at=row['created_at'], recorded_at=row['created_at'], status='recorded_note',
                    source=dict(row), project_ids=[pid], provenance='internal_project_note')

"""Owner-only enquiries, explicit customer matching and atomic order handover.

Provider adapters submit normalized messages; this module does not connect to a
mailbox or send messages. EML imports retain plain text and attachment metadata,
never execute HTML, download remote images or import attachment bytes.
"""
from contextlib import contextmanager
from datetime import date, datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
import hashlib
import json
import re
import sqlite3
import unicodedata
from urllib.parse import urlsplit
import uuid

from core import Problem, canonical, customer_values, digest, now_iso, text_field


MAX_EML_BYTES = 512 * 1024
MAX_MESSAGE = 40000
SOURCES = {'manual', 'gmail', 'whatsapp', 'import'}
STATUSES = {'new', 'callback', 'review', 'offer', 'awaiting_acceptance',
            'accepted', 'qualified', 'declined', 'converted'}
REVIEW_METHODS = {'', 'documents', 'on_site', 'zoom', 'other'}
ACCEPTANCE_CHANNELS = {'', 'phone', 'email', 'other'}
_UUID = re.compile(r'^[a-f0-9]{32}$')


def schema_statements():
    return [
        """CREATE TABLE IF NOT EXISTS inquiries(
          id TEXT PRIMARY KEY, source TEXT NOT NULL CHECK(source IN ('manual','gmail','whatsapp','import')),
          source_account TEXT NOT NULL, source_id TEXT, source_fingerprint TEXT NOT NULL,
          subject TEXT NOT NULL, message TEXT NOT NULL, sender_name TEXT NOT NULL,
          sender_email TEXT NOT NULL, sender_phone TEXT NOT NULL, received_at TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('new','callback','review','offer','awaiting_acceptance',
            'accepted','qualified','declined','converted')),
          review_method TEXT NOT NULL, acceptance_channel TEXT NOT NULL,
          customer_id TEXT REFERENCES customers(id), project_id TEXT REFERENCES projects(id),
          next_action TEXT NOT NULL, due_date TEXT, sevdesk_url TEXT NOT NULL,
          provenance TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
          created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(source,source_account,source_id),
          CHECK((status='converted' AND project_id IS NOT NULL AND customer_id IS NOT NULL)
             OR (status<>'converted' AND project_id IS NULL)))""",
        'CREATE INDEX IF NOT EXISTS inquiries_status ON inquiries(status,received_at,id)',
        """CREATE TABLE IF NOT EXISTS inquiry_requests(
          user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
          request_hash TEXT NOT NULL, result TEXT NOT NULL,
          PRIMARY KEY(user_id,request_id))""",
    ]


def ensure_sqlite_schema(office):
    if isinstance(office.db, sqlite3.Connection):
        with office.lock, office.db:
            for statement in schema_statements():
                office.db.execute(statement)


@contextmanager
def _transaction(office):
    """Do not prematurely commit an enclosing SQLite request transaction."""
    with office.lock:
        if not isinstance(office.db, sqlite3.Connection):
            with office.db:
                yield
            return
        name = 'inquiry_' + uuid.uuid4().hex
        office.db.execute('SAVEPOINT ' + name)
        try:
            yield
        except BaseException:
            office.db.execute('ROLLBACK TO SAVEPOINT ' + name)
            office.db.execute('RELEASE SAVEPOINT ' + name)
            raise
        else:
            office.db.execute('RELEASE SAVEPOINT ' + name)


def _text(value, field, maximum, *, required=False, multiline=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise Problem(400, 'Ungültiges Feld: ' + field)
    value = value.replace('\r\n', '\n').replace('\r', '\n') if multiline else value
    if any(ord(c) < 32 and (not multiline or c not in '\n\t') for c in value):
        raise Problem(400, 'Ungültiges Feld: ' + field)
    value = value.strip()
    if required and not value:
        raise Problem(400, 'Bitte ausfüllen: ' + field)
    return value


def _identifier(value, field='Anfrage-ID'):
    if not isinstance(value, str) or not _UUID.fullmatch(value):
        raise Problem(400, 'Ungültige ' + field)
    return value


def _email(value):
    value = _text(value, 'E-Mail', 254)
    if value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise Problem(400, 'Gültige E-Mail-Adresse eingeben')
    return value


def _email_key(value):
    return unicodedata.normalize('NFKC', value).casefold().strip()


def _phone_key(value):
    value = value.strip()
    international = value.startswith('+') or value.startswith('00')
    digits = ''.join(c for c in value if c.isascii() and c.isdigit())
    if international and value.startswith('00'):
        digits = digits[2:]
    return ('+' if international else '') + digits if len(digits) >= 6 else ''


def _due(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise Problem(400, 'Wiedervorlagedatum im Format JJJJ-MM-TT erwartet')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise Problem(400, 'Ungültiges Wiedervorlagedatum') from error


def _received(value):
    if not isinstance(value, str) or len(value) > 64:
        raise Problem(400, 'Eingangszeit mit Zeitzone erwartet')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone')
        return parsed.astimezone(timezone.utc).isoformat(timespec='seconds')
    except ValueError as error:
        raise Problem(400, 'Eingangszeit mit Zeitzone erwartet') from error


def _sevdesk(value):
    value = _text(value, 'Sevdesk-Verknüpfung', 2048)
    if not value:
        return ''
    try:
        url = urlsplit(value)
        host = (url.hostname or '').lower()
        valid = (url.scheme == 'https' and not url.username and not url.password
                 and url.port in (None, 443) and not any(c.isspace() for c in value)
                 and (host == 'sevdesk.de' or host.endswith('.sevdesk.de')))
    except ValueError:
        valid = False
    if not valid:
        raise Problem(400, 'Eine HTTPS-Verknüpfung zu Sevdesk erwartet')
    return value


class _PlainHTML(HTMLParser):
    """Text extraction only: no browser, URL access or attachment rendering."""
    hidden = {'script', 'style', 'iframe', 'object', 'svg', 'math', 'template', 'noscript'}
    blocks = {'br', 'p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'section', 'blockquote'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.hidden:
            self.skip.append(tag)
        elif not self.skip and tag in self.blocks:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
        elif tag in self.blocks:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return '\n'.join(line.strip() for line in ''.join(self.parts).splitlines() if line.strip())


def parse_eml(raw, *, received_at):
    """Return a bounded normalized message plus metadata; raw MIME is not saved."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_EML_BYTES:
        raise Problem(413, 'EML-Datei mit höchstens 512 KiB erwartet')
    try:
        mail = BytesParser(policy=policy.default).parsebytes(raw)
        for field in ('From', 'Subject', 'Message-ID', 'Date'):
            if len(mail.get_all(field, [])) > 1:
                raise Problem(400, 'Mehrdeutige E-Mail-Kopfzeile: ' + field)
        senders = getaddresses([str(mail.get('From', ''))])
        if len(senders) > 1:
            raise Problem(400, 'Genau einen E-Mail-Absender erwartet')
        sender_name, sender_email = senders[0] if senders else ('', '')
        warnings = []
        try:
            sender_email = _email(sender_email)
        except Problem:
            sender_email = ''
            warnings.append('Absenderadresse konnte nicht übernommen werden.')
        plain, html, attachments = [], [], []
        count = 0

        def collect(part, depth=0):
            nonlocal count
            count += 1
            if count > 100 or depth > 15:
                raise Problem(400, 'Die E-Mail enthält zu viele verschachtelte Teile')
            filename = part.get_filename()
            attached = part.get_content_disposition() == 'attachment' or bool(filename)
            if attached or part.get_content_type() == 'message/rfc822':
                name = re.split(r'[/\\]', filename or 'Anhang')[-1]
                name = ''.join(c for c in name if ord(c) >= 32)[:200] or 'Anhang'
                content = part.get_payload(decode=True)
                attachments.append({'filename': name, 'media_type': part.get_content_type()[:100],
                                    'size': len(content) if isinstance(content, bytes) else None})
                if len(attachments) > 30:
                    raise Problem(400, 'Die E-Mail enthält zu viele Anhänge')
                return
            if part.is_multipart():
                for child in part.iter_parts():
                    collect(child, depth + 1)
                return
            if part.get_content_type() not in ('text/plain', 'text/html'):
                return
            encoded = part.get_payload(decode=True) or b''
            try:
                value = encoded.decode(part.get_content_charset() or 'utf-8', errors='replace')
            except LookupError:
                value = encoded.decode('utf-8', errors='replace')
                warnings.append('Unbekannte Zeichenkodierung wurde ersetzt.')
            if part.get_content_type() == 'text/plain':
                plain.append(value)
            else:
                cleaner = _PlainHTML()
                cleaner.feed(value)
                cleaner.close()
                html.append(cleaner.text())

        collect(mail)
        message = '\n\n'.join(plain if any(p.strip() for p in plain) else html).strip()
        if not message:
            raise Problem(400, 'Die E-Mail enthält keinen lesbaren Nachrichtentext')
        timestamp = received_at
        if mail.get('Date'):
            try:
                parsed = parsedate_to_datetime(str(mail['Date']))
                if parsed.tzinfo is None:
                    raise ValueError('timezone')
                timestamp = parsed.astimezone(timezone.utc).isoformat(timespec='seconds')
            except (ValueError, TypeError, OverflowError):
                warnings.append('Eingangszeit wurde beim Import gesetzt.')
        raw_hash = hashlib.sha256(raw).hexdigest()
        message_id = ' '.join(str(mail.get('Message-ID', '')).split())
        if len(message_id) > 512:
            raise Problem(400, 'Die Nachrichtenkennung ist zu lang')
        if attachments:
            warnings.append('Anhänge sind nur vermerkt und wurden nicht übernommen.')
        data = {
            'subject': ' '.join(str(mail.get('Subject', '')).split()) or '(Ohne Betreff)',
            'message': message,
            'sender_name': ' '.join(sender_name.split()),
            'sender_email': sender_email,
            'sender_phone': '',
            'received_at': timestamp,
            'source_id': message_id or 'sha256:' + raw_hash,
        }
        provenance = {'format': 'eml', 'message_id': message_id, 'raw_sha256': raw_hash,
                      'attachments': attachments, 'warnings': list(dict.fromkeys(warnings))}
        return data, provenance
    except Problem:
        raise
    except (ValueError, TypeError, RecursionError, UnicodeError) as error:
        raise Problem(400, 'Die EML-Datei konnte nicht sicher gelesen werden') from error


class Inquiries:
    def __init__(self, office, *, clock=now_iso):
        self.office, self.db, self.clock = office, office.db, clock

    def _authorize(self, actor):
        self.office.require(actor, ('owner',))
        row = self.db.execute('SELECT role,active FROM users WHERE id=?', (actor.get('id'),)).fetchone()
        if not row or row['active'] != 1 or row['role'] != 'owner':
            raise Problem(403, 'Anfragen und Kundenzuordnung sind der Geschäftsführung vorbehalten')

    def _row(self, identifier):
        _identifier(identifier)
        row = self.db.execute('SELECT * FROM inquiries WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise Problem(404, 'Anfrage nicht verfügbar')
        return row

    def _replay(self, actor, request_id, fingerprint):
        row = self.db.execute('SELECT request_hash,result FROM inquiry_requests WHERE user_id=? AND request_id=?',
                              (actor['id'], request_id)).fetchone()
        if row:
            if row['request_hash'] != fingerprint:
                raise Problem(409, 'Diese Anfrage-ID wurde bereits für einen anderen Vorgang verwendet')
            return json.loads(row['result'])
        return None

    def _receipt(self, actor, request_id, fingerprint, result):
        self.db.execute('INSERT INTO inquiry_requests(user_id,request_id,request_hash,result) VALUES(?,?,?,?)',
                        (actor['id'], request_id, fingerprint, canonical(result)))
        return result

    def _candidates(self, record):
        email, phone = _email_key(record['sender_email']), _phone_key(record['sender_phone'])
        result = []
        if not email and not phone:
            return result
        for row in self.db.execute('SELECT id,name,contact,email,phone,address,active FROM customers WHERE active=1'):
            reasons = []
            if email and _email_key(row['email']) == email:
                reasons.append('email')
            if phone and _phone_key(row['phone']) == phone:
                reasons.append('phone')
            if reasons:
                result.append({**dict(row), 'match_reasons': reasons})
        return sorted(result, key=lambda item: (item['name'].casefold(), item['id']))

    def _record(self, row, *, summary=False):
        result = {key: row[key] for key in (
            'id', 'source', 'source_account', 'source_id', 'subject', 'sender_name', 'sender_email',
            'sender_phone', 'received_at', 'status', 'review_method', 'acceptance_channel', 'customer_id',
            'project_id', 'next_action', 'due_date', 'sevdesk_url', 'revision', 'created_by', 'created_at', 'updated_at')}
        result['message_preview'] = row['message'][:180]
        result['customer'] = None
        result['project'] = None
        if row['customer_id']:
            customer = self.db.execute('SELECT id,name,active FROM customers WHERE id=?',
                                       (row['customer_id'],)).fetchone()
            result['customer'] = dict(customer) if customer else None
        if row['project_id']:
            project = self.db.execute('SELECT id,name,customer_id,customer FROM projects WHERE id=?',
                                      (row['project_id'],)).fetchone()
            result['project'] = dict(project) if project else None
        if not summary:
            result['message'] = row['message']
            result['provenance'] = json.loads(row['provenance'])
            result['candidate_customers'] = self._candidates(result)
            if row['source'] == 'gmail':
                from inquiry_attachments import InquiryAttachments
                result['attachments'] = InquiryAttachments(self.office).summary(row['id'])
        return result

    def list(self, actor, *, status=None, limit=200):
        if status is not None and (not isinstance(status, str) or status not in STATUSES):
            raise Problem(400, 'Unbekannter Anfragestatus')
        if type(limit) is not int or not 1 <= limit <= 500:
            raise Problem(400, 'Höchstens 500 Anfragen pro Abruf erwartet')
        with self.office.lock:
            self._authorize(actor)
            query = 'SELECT * FROM inquiries'
            parameters = []
            if status is not None:
                query += ' WHERE status=?'
                parameters.append(status)
            query += ' ORDER BY received_at DESC,id LIMIT ?'
            return [self._record(row, summary=True) for row in self.db.execute(query, (*parameters, limit)).fetchall()]

    def get(self, actor, identifier):
        with self.office.lock:
            self._authorize(actor)
            return self._record(self._row(identifier))

    def connections(self, actor):
        with self.office.lock:
            self._authorize(actor)
        return {'automatic_ingestion': False, 'manual_import': {'eml': True, 'max_eml_bytes': MAX_EML_BYTES,
                'message': True}, 'providers': [
            {'id': 'gmail', 'state': 'not_connected', 'manual_import_available': True},
            {'id': 'whatsapp', 'state': 'not_connected', 'manual_import_available': True},
        ]}

    def create(self, actor, data):
        return self._create(actor, data, provenance={'format': 'normalized_message', 'attachments': [], 'warnings': []})

    def _create(self, actor, data, *, provenance):
        allowed = {'request_id', 'source', 'source_account', 'source_id', 'subject', 'message',
                   'sender_name', 'sender_email', 'sender_phone', 'received_at'}
        if not isinstance(data, dict) or set(data) - allowed:
            raise Problem(400, 'Gültige Anfragenachricht erwartet')
        request_id = _identifier(data.get('request_id'))
        source = data.get('source', 'manual')
        if not isinstance(source, str) or source not in SOURCES:
            raise Problem(400, 'Unbekannter Eingangskanal')
        values = {
            'source': source,
            'source_account': _text(data.get('source_account', 'manual'), 'Postfach/Kanal', 254, required=True),
            'source_id': _text(data.get('source_id', ''), 'Nachrichtenkennung', 512) or None,
            'subject': _text(data.get('subject'), 'Betreff', 300, required=True),
            'message': _text(data.get('message'), 'Nachricht', MAX_MESSAGE, required=True, multiline=True),
            'sender_name': _text(data.get('sender_name', ''), 'Absender', 200),
            'sender_email': _email(data.get('sender_email', '')),
            'sender_phone': _text(data.get('sender_phone', ''), 'Telefon', 100),
        }
        received = _received(data.get('received_at', self.clock()))
        source_fingerprint = digest(canonical({'message': values, 'provenance': provenance}))
        fingerprint = digest(canonical({'operation': 'create', 'data': values, 'provenance': provenance,
                                        'received_at': _received(data['received_at'])
                                        if 'received_at' in data and provenance['format'] != 'eml' else None}))
        with _transaction(self.office):
            self._authorize(actor)
            previous = self._replay(actor, request_id, fingerprint)
            if previous is not None:
                return previous
            if values['source_id']:
                duplicate = self.db.execute('SELECT * FROM inquiries WHERE source=? AND source_account=? AND source_id=?',
                                             (source, values['source_account'], values['source_id'])).fetchone()
                if duplicate:
                    if duplicate['source_fingerprint'] != source_fingerprint:
                        raise Problem(409, 'Diese Nachrichtenkennung gehört zu einem anderen Inhalt')
                    return self._receipt(actor, request_id, fingerprint, self._record(duplicate))
            identifier, timestamp = uuid.uuid4().hex, self.clock()
            self.db.execute('''INSERT INTO inquiries(id,source,source_account,source_id,source_fingerprint,
                subject,message,sender_name,sender_email,sender_phone,received_at,status,review_method,
                acceptance_channel,customer_id,project_id,next_action,due_date,sevdesk_url,provenance,
                revision,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (identifier, source, values['source_account'], values['source_id'], source_fingerprint,
                 values['subject'], values['message'], values['sender_name'], values['sender_email'],
                 values['sender_phone'], received, 'new', '', '', None, None, '', None, '', canonical(provenance),
                 1, actor['id'], timestamp, timestamp))
            self.office.audit(actor, 'inquiry.created', identifier)
            return self._receipt(actor, request_id, fingerprint, self._record(self._row(identifier)))

    def update(self, actor, identifier, data):
        allowed = {'request_id', 'revision', 'status', 'customer_id', 'next_action', 'due_date',
                   'sevdesk_url', 'review_method', 'acceptance_channel'}
        if not isinstance(data, dict) or set(data) - allowed or not set(data) - {'request_id', 'revision'}:
            raise Problem(400, 'Anfragestatus oder nächste Schritte erwartet')
        request_id = _identifier(data.get('request_id'))
        revision = data.get('revision')
        if type(revision) is not int or revision < 1:
            raise Problem(400, 'Ausgangsversion der Anfrage erwartet')
        changes = {}
        if 'status' in data:
            if not isinstance(data['status'], str) or data['status'] not in STATUSES - {'converted'}:
                raise Problem(400, 'Ungültiger Anfragestatus; Projektübernahme gesondert bestätigen')
            changes['status'] = data['status']
        for field, options in (('review_method', REVIEW_METHODS), ('acceptance_channel', ACCEPTANCE_CHANNELS)):
            if field in data:
                if not isinstance(data[field], str) or data[field] not in options:
                    raise Problem(400, 'Ungültige Auswahl: ' + field)
                changes[field] = data[field]
        if 'customer_id' in data:
            changes['customer_id'] = _identifier(data['customer_id'], 'Kunden-ID') if data['customer_id'] is not None else None
        if 'next_action' in data:
            changes['next_action'] = _text(data['next_action'], 'Nächster Schritt', 2000, multiline=True)
        if 'due_date' in data:
            changes['due_date'] = _due(data['due_date'])
        if 'sevdesk_url' in data:
            changes['sevdesk_url'] = _sevdesk(data['sevdesk_url'])
        fingerprint = digest(canonical({'operation': 'update', 'id': identifier, 'data': data}))
        with _transaction(self.office):
            self._authorize(actor)
            previous = self._replay(actor, request_id, fingerprint)
            if previous is not None:
                return previous
            current = self._row(identifier)
            if current['revision'] != revision or current['status'] == 'converted':
                raise Problem(409, 'Anfrage wurde inzwischen geändert oder bereits übernommen; neu laden')
            if changes.get('customer_id'):
                customer = self.office.customer(actor, changes['customer_id'])
                if customer['active'] != 1:
                    raise Problem(409, 'Kunde ist archiviert; zuerst reaktivieren')
            next_status = changes.get('status', current['status'])
            channel = changes.get('acceptance_channel', current['acceptance_channel'])
            if next_status == 'accepted' and not channel:
                raise Problem(400, 'Für die bestätigte Zusage Telefon, E-Mail oder einen anderen Weg angeben')
            query = 'UPDATE inquiries SET ' + ','.join(field + '=?' for field in changes)
            self.db.execute(query + ',revision=revision+1,updated_at=? WHERE id=?',
                            (*changes.values(), self.clock(), identifier))
            self.office.audit(actor, 'inquiry.updated', identifier)
            return self._receipt(actor, request_id, fingerprint, self._record(self._row(identifier)))

    def convert(self, actor, identifier, data):
        if (not isinstance(data, dict) or set(data) - {'request_id', 'revision', 'project_name', 'customer_id', 'customer'}
                or ('customer_id' in data) == ('customer' in data)):
            raise Problem(400, 'Projektname und genau einen bestehenden oder neuen Kunden bestätigen')
        request_id = _identifier(data.get('request_id'))
        revision = data.get('revision')
        if type(revision) is not int or revision < 1:
            raise Problem(400, 'Ausgangsversion der Anfrage erwartet')
        project_name = text_field(data.get('project_name'), 'Projekt')
        customer_id = _identifier(data['customer_id'], 'Kunden-ID') if 'customer_id' in data else None
        customer = customer_values(data['customer']) if 'customer' in data else None
        if customer and not customer['active']:
            raise Problem(400, 'Ein neuer Projektkunde muss aktiv sein')
        fingerprint = digest(canonical({'operation': 'convert', 'id': identifier, 'data': data}))
        with _transaction(self.office):
            self._authorize(actor)
            previous = self._replay(actor, request_id, fingerprint)
            if previous is not None:
                return previous
            current = self._row(identifier)
            if current['revision'] != revision or current['status'] == 'converted':
                raise Problem(409, 'Anfrage wurde inzwischen geändert oder bereits übernommen; neu laden')
            if current['status'] == 'declined':
                raise Problem(409, 'Abgelehnte Anfrage vor der Projektanlage ausdrücklich reaktivieren')
            if customer_id:
                selected = self.office.customer(actor, customer_id)
                if selected['active'] != 1:
                    raise Problem(409, 'Kunde ist archiviert; zuerst reaktivieren')
            else:
                customer_id = self.office.insert_customer(customer)
                self.office.audit(actor, 'customer.created', customer_id)
                selected = self.office.customer(actor, customer_id)
            project_id = uuid.uuid4().hex
            self.db.execute('INSERT INTO projects(id,name,customer,customer_id) VALUES(?,?,?,?)',
                            (project_id, project_name, selected['name'], customer_id))
            self.office.audit(actor, 'project.created', project_id)
            self.db.execute("UPDATE inquiries SET status='converted',customer_id=?,project_id=?,revision=revision+1,"
                            'updated_at=? WHERE id=?', (customer_id, project_id, self.clock(), identifier))
            self.office.audit(actor, 'inquiry.converted', identifier)
            result = {'inquiry': self._record(self._row(identifier)),
                      'project': self.office.project(actor, project_id)}
            return self._receipt(actor, request_id, fingerprint, result)

    def import_eml(self, actor, raw, *, request_id, source_account='manual-import'):
        self._authorize(actor)
        data, provenance = parse_eml(raw, received_at=self.clock())
        data.update(request_id=request_id, source='import', source_account=source_account)
        return self._create(actor, data, provenance=provenance)

"""Smartplan Office foundation. Local development service; no public deployment."""
import base64
import hashlib
import hmac
import io
import json
import re
import secrets
import sqlite3
import threading
import time
import uuid
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Flowable


class Problem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def text_field(value, name, maximum=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise Problem(400, f"Ungültiges Feld: {name}")
    return value.strip()


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310000).hex()


ROLES = ("owner", "manager", "technician", "accountant")


def validate_password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 512:
        raise Problem(400, "Passwort benötigt 12 bis 512 Zeichen")


class Signature(Flowable):
    width, height = 420, 110

    def __init__(self, strokes):
        super().__init__()
        self.width, self.height = 420, 110
        self.strokes = strokes

    def draw(self):
        self.canv.setStrokeColor(colors.HexColor("#172b38"))
        self.canv.setLineWidth(1.5)
        for stroke in self.strokes:
            p = self.canv.beginPath()
            p.moveTo(stroke[0][0] * self.width, (1 - stroke[0][1]) * self.height)
            for x, y in stroke[1:]:
                p.lineTo(x * self.width, (1-y) * self.height)
            self.canv.drawPath(p)
        self.canv.setStrokeColor(colors.HexColor("#cdd8dc"))
        self.canv.line(0, 0, self.width, 0)


def make_pdf(report):
    content = report["content"]
    stream = io.BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=(595, 842), leftMargin=48, rightMargin=48,
                            topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    story = [Paragraph("SMARTPLAN HOFMANN", styles["Title"]), Spacer(1, 12),
             Paragraph(escape(content["kind"]), styles["Heading1"])]
    for label, value in [("Projekt", content["project_name"]), ("Kunde", content["customer"]),
                         ("Dokument", report["id"]), ("Erstellt (UTC)", content["created_at"])]:
        story.append(Paragraph(f"<b>{label}:</b> {escape(str(value))}", styles["Normal"]))
    story += [Spacer(1, 16), Paragraph("Leistungen / gelieferte Positionen", styles["Heading2"]),
              Paragraph(escape(content["description"]).replace("\n", "<br/>"), styles["Normal"]),
              Spacer(1, 20)]
    if report["status"] == "signed":
        story += [Paragraph("Unterschrift", styles["Heading2"]), Signature(report["strokes"]),
                  Spacer(1, 10), Paragraph(escape(report["signer"]), styles["Normal"]),
                  Paragraph("Unterzeichnet (UTC): " + escape(report["signed_at"]), styles["Normal"])]
    else:
        story.append(Paragraph("ENTWURF - noch nicht unterzeichnet", styles["Heading2"]))
    story += [Spacer(1, 18), Paragraph("Dokumentinhalt SHA-256:", styles["Normal"]),
              Paragraph(report["content_hash"], styles["Code"])]
    doc.build(story)
    return stream.getvalue()


def now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


CUSTOMER_FIELDS = ("name", "contact", "email", "phone", "address", "notes", "active")


def customer_values(changes, previous=None):
    if not isinstance(changes, dict) or not changes or set(changes) - set(CUSTOMER_FIELDS):
        raise Problem(400, "Ungültige Kundenangaben")
    value = {"name": "", "contact": "", "email": "", "phone": "", "address": "", "notes": "", "active": True}
    if previous:
        value.update({key: previous[key] for key in CUSTOMER_FIELDS})
        value["active"] = bool(value["active"])
    value.update(changes)
    value["name"] = text_field(value["name"], "Kundenname")
    for field, maximum in (("contact", 200), ("email", 254), ("phone", 100), ("address", 2000), ("notes", 5000)):
        if not isinstance(value[field], str) or len(value[field]) > maximum:
            raise Problem(400, "Ungültiges Kundenfeld: " + field)
        value[field] = value[field].strip()
    if value["email"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value["email"]):
        raise Problem(400, "Gültige E-Mail-Adresse eingeben")
    if type(value["active"]) is not bool:
        raise Problem(400, "Aktiv muss ein Wahrheitswert sein")
    return value


def customer_key(name, address=""):
    def normalize(text):
        return " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return digest(canonical([normalize(name), normalize(address)]))


class Office:
    integrity_error = sqlite3.IntegrityError
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE, salt TEXT,
          password TEXT, role TEXT, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expiry REAL);
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT,customer TEXT);
        CREATE TABLE IF NOT EXISTS assignments(user_id TEXT REFERENCES users(id),project_id TEXT REFERENCES projects(id),
          PRIMARY KEY(user_id,project_id));
        CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,project_id TEXT REFERENCES projects(id),
          payload TEXT,pdf BLOB,pdf_hash TEXT,onedrive_id TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id TEXT,action TEXT,object_id TEXT,at TEXT);
        CREATE TABLE IF NOT EXISTS secrets(name TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS plan_versions(
            id TEXT NOT NULL, revision INTEGER NOT NULL, project_id TEXT NOT NULL REFERENCES projects(id),
            payload TEXT NOT NULL, PRIMARY KEY(id,revision));
            CREATE TABLE IF NOT EXISTS plan_requests(
            user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
            project_id TEXT NOT NULL REFERENCES projects(id), request_hash TEXT NOT NULL,
            result TEXT NOT NULL, PRIMARY KEY(user_id,request_id));
            CREATE TABLE IF NOT EXISTS plan_sessions(
            token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            expiry DOUBLE PRECISION NOT NULL, credential TEXT NOT NULL);
        """)
        self.db.commit()
        try:
            self.migrate_customers()
            from plan_deletions import schema_statements
            with self.db:
                for statement in schema_statements():
                    self.db.execute(statement)
                from workspace_api import schema_statements as workspace_schema
                for statement in workspace_schema():
                    self.db.execute(statement)
                from inquiry_attachments import schema_statements as attachment_schema
                for statement in attachment_schema('BLOB'):
                    self.db.execute(statement)
                from external_integrations import schema_statements as integration_schema
                for statement in integration_schema():
                    self.db.execute(statement)
                from integration_bridge import schema_statements as bridge_schema
                for statement in bridge_schema():
                    self.db.execute(statement)
        except Exception:
            self.db.close()
            raise
        self.failed_logins = {}

    def migrate_customers(self):
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise RuntimeError("Diese Datenbank benötigt eine neuere Smartplan-Version")
        if version == 1:
            return
        # A single additive transaction; no existing payload, PDF or account is rewritten.
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.db.execute("PRAGMA user_version").fetchone()[0] == 1:
                return
            self.db.execute("""CREATE TABLE customers(
                id TEXT PRIMARY KEY, name TEXT NOT NULL, contact TEXT NOT NULL,
                email TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL,
                notes TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
                dedupe_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            self.db.execute("ALTER TABLE projects ADD COLUMN customer_id TEXT REFERENCES customers(id)")
            self.db.execute("CREATE INDEX projects_customer ON projects(customer_id)")
            for project in self.db.execute("SELECT id,customer FROM projects ORDER BY rowid").fetchall():
                value = customer_values({"name": project["customer"]})
                key = customer_key(value["name"])
                row = self.db.execute("SELECT id FROM customers WHERE dedupe_key=?", (key,)).fetchone()
                customer_id = row["id"] if row else self.insert_customer(value)
                self.db.execute("UPDATE projects SET customer_id=? WHERE id=?", (customer_id, project["id"]))
            self.db.execute("PRAGMA user_version=1")

    def insert_customer(self, value):
        customer_id, timestamp = uuid.uuid4().hex, now_iso()
        try:
            self.db.execute("INSERT INTO customers VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                customer_id, value["name"], value["contact"], value["email"], value["phone"],
                value["address"], value["notes"], int(value["active"]),
                customer_key(value["name"], value["address"]), timestamp, timestamp))
        except self.integrity_error:
            raise Problem(409, "Kunde mit diesem Namen und dieser Adresse existiert bereits; auch archivierte Kunden prüfen")
        return customer_id

    def customer(self, actor, customer_id):
        self.require(actor, ("owner",))
        with self.lock:
            row = self.db.execute("SELECT id,name,contact,email,phone,address,notes,active,created_at,updated_at "
                                  "FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not row:
                raise Problem(404, "Kunde nicht verfügbar")
            return dict(row)

    def customers(self, actor):
        self.require(actor, ("owner",))
        with self.lock:
            return [dict(row) for row in self.db.execute(
                "SELECT c.id,c.name,c.contact,c.email,c.phone,c.address,c.notes,c.active,c.created_at,c.updated_at,"
                "(SELECT COUNT(*) FROM projects p WHERE p.customer_id=c.id) AS project_count "
                "FROM customers c ORDER BY lower(c.name),c.id")]

    def create_customer(self, actor, changes):
        self.require(actor, ("owner",))
        value = customer_values(changes)
        with self.lock, self.db:
            customer_id = self.insert_customer(value)
            self.audit(actor, "customer.created", customer_id)
            return self.customer(actor, customer_id)

    def update_customer(self, actor, customer_id, changes):
        self.require(actor, ("owner",))
        with self.lock, self.db:
            value = customer_values(changes, self.customer(actor, customer_id))
            try:
                self.db.execute("UPDATE customers SET name=?,contact=?,email=?,phone=?,address=?,notes=?,active=?,"
                                "dedupe_key=?,updated_at=? WHERE id=?", (
                    value["name"], value["contact"], value["email"], value["phone"], value["address"], value["notes"],
                    int(value["active"]), customer_key(value["name"], value["address"]), now_iso(), customer_id))
            except self.integrity_error:
                raise Problem(409, "Kunde mit diesem Namen und dieser Adresse existiert bereits")
            # Reports contain independent, immutable snapshots of their original customer name.
            self.db.execute("UPDATE projects SET customer=? WHERE customer_id=?", (value["name"], customer_id))
            self.audit(actor, "customer.updated", customer_id)
            return self.customer(actor, customer_id)

    def project_customer(self, actor, project_id, customer_id):
        self.require(actor, ("owner",))
        customer_id = text_field(customer_id, "Kunde", 32)
        with self.lock, self.db:
            self.project(actor, project_id)
            customer = self.customer(actor, customer_id)
            if not customer["active"]:
                raise Problem(409, "Kunde ist archiviert; zuerst reaktivieren")
            self.db.execute("UPDATE projects SET customer_id=?,customer=? WHERE id=?",
                            (customer_id, customer["name"], project_id))
            self.audit(actor, "project.customer_changed", project_id)
            return self.project(actor, project_id)

    def audit(self, user, action, object_id):
        self.db.execute("INSERT INTO audit(user_id,action,object_id,at) VALUES(?,?,?,?)",
                        (user["id"], action, object_id, now_iso()))

    def add_user(self, email, password, role="technician"):
        if role not in ROLES:
            raise Problem(400, "Unbekannte Rolle")
        validate_password(password)
        email = text_field(email, "E-Mail", 254).lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise Problem(400, "Ungültige E-Mail-Adresse")
        salt, user_id = secrets.token_hex(16), uuid.uuid4().hex
        with self.lock, self.db:
            try:
                self.db.execute("INSERT INTO users(id,email,salt,password,role) VALUES(?,?,?,?,?)",
                                (user_id,email,salt,password_hash(password,salt),role))
            except self.integrity_error:
                raise Problem(409, "Benutzer existiert bereits")
        return user_id

    def users(self, actor):
        self.require(actor, ("owner",))
        with self.lock:
            return [dict(r) for r in self.db.execute(
                "SELECT id,email,role,active FROM users ORDER BY email")]

    def create_user(self, actor, email, password, role):
        self.require(actor, ("owner",))
        with self.lock, self.db:
            user_id = self.add_user(email, password, role)
            self.audit(actor, "user.created", user_id)
            return user_id

    def update_user(self, actor, user_id, changes):
        self.require(actor, ("owner",))
        if not changes or set(changes) - {"role", "active", "password"}:
            raise Problem(400, "Ungültige Benutzeränderung")
        if "role" in changes and changes["role"] not in ROLES:
            raise Problem(400, "Unbekannte Rolle")
        if "active" in changes and type(changes["active"]) is not bool:
            raise Problem(400, "Aktiv muss ein Wahrheitswert sein")
        if "password" in changes:
            validate_password(changes["password"])
        with self.lock, self.db:
            row = self.db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                raise Problem(404, "Benutzer nicht verfügbar")
            role = changes.get("role", row["role"])
            active = changes.get("active", bool(row["active"]))
            if actor["id"] == user_id and (role != row["role"] or not active):
                raise Problem(409, "Eigene Rolle und eigenen Zugang nicht sperren")
            if row["role"] == "owner" and row["active"] and (role != "owner" or not active):
                count = self.db.execute("SELECT COUNT(*) FROM users WHERE role='owner' AND active=1").fetchone()[0]
                if count <= 1:
                    raise Problem(409, "Mindestens eine aktive Geschäftsführung ist erforderlich")
            self.db.execute("UPDATE users SET role=?,active=? WHERE id=?", (role, int(active), user_id))
            if "password" in changes:
                salt = secrets.token_hex(16)
                self.db.execute("UPDATE users SET salt=?,password=? WHERE id=?",
                                (salt, password_hash(changes["password"], salt), user_id))
            if not active or role != row["role"] or "password" in changes:
                self.db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
                self.db.execute("DELETE FROM plan_sessions WHERE user_id=?", (user_id,))
            self.audit(actor, "user.updated", user_id)
            return dict(self.db.execute("SELECT id,email,role,active FROM users WHERE id=?", (user_id,)).fetchone())

    def assignments(self, actor, project_id):
        self.require(actor, ("owner",))
        with self.lock:
            self.project(actor, project_id)
            return [dict(r) for r in self.db.execute(
                "SELECT u.id,u.email,u.role,u.active FROM users u JOIN assignments a ON u.id=a.user_id "
                "WHERE a.project_id=? ORDER BY u.email", (project_id,))]

    def assign(self, actor, project_id, user_id, remove=False):
        self.require(actor, ("owner",))
        if type(remove) is not bool:
            raise Problem(400, "Entfernen muss ein Wahrheitswert sein")
        with self.lock, self.db:
            self.project(actor, project_id)
            if not self.db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
                raise Problem(404, "Benutzer nicht verfügbar")
            if remove:
                self.db.execute("DELETE FROM assignments WHERE user_id=? AND project_id=?", (user_id, project_id))
            else:
                self.db.execute("INSERT INTO assignments VALUES(?,?) ON CONFLICT DO NOTHING", (user_id, project_id))
            self.audit(actor, "assignment.removed" if remove else "assignment.added", project_id)

    def login(self, email, password):
        email = text_field(email, "E-Mail", 254).lower()
        if not isinstance(password, str) or len(password) > 512:
            raise Problem(401, "Anmeldung fehlgeschlagen")
        with self.lock, self.db:
            failures = [t for t in self.failed_logins.get(email, []) if t > time.time()-300]
            self.failed_logins[email] = failures
            if len(failures) >= 5:
                raise Problem(429, "Bitte in fünf Minuten erneut versuchen")
            user = self.db.execute("SELECT * FROM users WHERE email=? AND active=1", (email,)).fetchone()
            salt = user["salt"] if user else "00"*16
            calculated = password_hash(password, salt)
            if not user or not hmac.compare_digest(calculated,user["password"]):
                failures.append(time.time())
                raise Problem(401, "Anmeldung fehlgeschlagen")
            self.failed_logins.pop(email, None)
            token = secrets.token_urlsafe(32)
            self.db.execute("INSERT INTO sessions VALUES(?,?,?)",(digest(token),user["id"],time.time()+8*3600))
            self.audit(user,"login",user["id"])
            return token

    def user(self, token):
        with self.lock:
            row = self.db.execute("SELECT u.id,u.email,u.role FROM users u JOIN sessions s ON u.id=s.user_id "
                                  "WHERE s.token=? AND s.expiry>? AND u.active=1",(digest(token),time.time())).fetchone()
            if not row:
                raise Problem(401,"Bitte anmelden")
            return dict(row)

    def require(self, user, roles):
        if user["role"] not in roles:
            raise Problem(403,"Keine Berechtigung")

    def project(self, user, project_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM projects WHERE id=?",(project_id,)).fetchone()
            if not row or (user["role"] != "owner" and not self.db.execute(
                "SELECT 1 FROM assignments WHERE user_id=? AND project_id=?",(user["id"],project_id)).fetchone()):
                raise Problem(404,"Projekt nicht verfügbar")
            return dict(row)

    def projects(self, user):
        with self.lock:
            if user["role"] == "owner":
                return [dict(r) for r in self.db.execute("SELECT * FROM projects ORDER BY name")]
            return [dict(r) for r in self.db.execute("SELECT p.* FROM projects p JOIN assignments a "
                    "ON p.id=a.project_id WHERE a.user_id=? ORDER BY name",(user["id"],))]

    def add_project(self, user, name, customer=None, customer_id=None):
        self.require(user,("owner",))
        name = text_field(name,"Projekt")
        project_id = uuid.uuid4().hex
        with self.lock, self.db:
            if customer_id is not None:
                record = self.customer(user, text_field(customer_id, "Kunde", 32))
                if not record["active"]:
                    raise Problem(409, "Kunde ist archiviert; zuerst reaktivieren")
            else:
                value = customer_values({"name": customer})
                row = self.db.execute("SELECT id FROM customers WHERE dedupe_key=?", (customer_key(value["name"]),)).fetchone()
                customer_id = row["id"] if row else self.insert_customer(value)
                if not row:
                    self.audit(user, "customer.created", customer_id)
                record = self.customer(user, customer_id)
                if not record["active"]:
                    raise Problem(409, "Kunde ist archiviert; zuerst reaktivieren")
            self.db.execute("INSERT INTO projects(id,name,customer,customer_id) VALUES(?,?,?,?)",
                            (project_id,name,record["name"],customer_id))
            self.audit(user,"project.created",project_id)
        return project_id

    def plans(self, user, project_id):
        with self.lock:
            self.project(user, project_id)
            return [json.loads(row[0]) for row in self.db.execute(
                'SELECT p.payload FROM plan_versions p WHERE p.project_id=? AND p.revision='
                '(SELECT MAX(v.revision) FROM plan_versions v WHERE v.id=p.id) AND NOT EXISTS '
                "(SELECT 1 FROM plan_deletions d WHERE d.kind='plan' AND d.object_id=p.id) ORDER BY p.id", (project_id,))]

    def plan(self, user, project_id, plan_id):
        with self.lock:
            self.project(user, project_id)
            from plan_deletions import assert_object_live
            assert_object_live(self.db, 'plan', plan_id, project_id)
            row = self.db.execute('SELECT payload FROM plan_versions WHERE id=? AND project_id=? '
                                  'ORDER BY revision DESC LIMIT 1', (plan_id, project_id)).fetchone()
            if not row:
                raise Problem(404, 'Plan nicht verfügbar')
            return json.loads(row[0])

    def save_plan(self, user, project_id, data, plan_id=None):
        from plans import validate_drawing
        self.require(user, ('owner', 'manager', 'technician'))
        if set(data) - {'request_id'} != ({'title', 'walls', 'revision'} if plan_id else {'title', 'walls'}):
            raise Problem(400, 'Plantitel, Wände und gegebenenfalls Ausgangsversion erwartet')
        title = text_field(data.get('title'), 'Plantitel', 200)
        walls = validate_drawing(data.get('walls'))
        request_id = data.get('request_id')
        if 'request_id' in data and (not isinstance(request_id, str) or not re.fullmatch(r'[a-f0-9]{32}', request_id)):
            raise Problem(400, 'Eindeutige Synchronisierungs-ID erwartet')
        fingerprint = digest(canonical(dict(project_id=project_id, plan_id=plan_id, data=data)))
        with self.lock, self.db:
            self.project(user, project_id)
            from plan_deletions import assert_create_live, assert_object_live
            if plan_id:
                assert_object_live(self.db, 'plan', plan_id, project_id)
            else:
                assert_create_live(self.db, 'plan', project_id, user['id'], request_id)
            if request_id:
                previous = self.db.execute('SELECT request_hash,result FROM plan_requests WHERE user_id=? AND request_id=?',
                                           (user['id'], request_id)).fetchone()
                if previous:
                    if previous['request_hash'] != fingerprint:
                        raise Problem(409, 'Synchronisierungs-ID wurde bereits für einen anderen Inhalt verwendet')
                    saved = json.loads(previous['result'])
                    if saved.get('deleted'):
                        raise Problem(410, 'Dieser Plan wurde gelöscht')
                    return saved
            revision = 1
            if plan_id:
                current = self.plan(user, project_id, plan_id)
                if type(data['revision']) is not int or data['revision'] != current['revision']:
                    raise Problem(409, 'Der Plan wurde inzwischen geändert. Neu laden; Ihre Zeichnung bleibt geöffnet.')
                revision = current['revision'] + 1
            plan_id = plan_id or uuid.uuid4().hex
            result = dict(id=plan_id, project_id=project_id, title=title, revision=revision,
                          status='draft', units='unitless', walls=walls, updated_at=now_iso(), updated_by=user['id'])
            self.db.execute('INSERT INTO plan_versions(id,revision,project_id,payload) VALUES(?,?,?,?)',
                            (plan_id, revision, project_id, canonical(result)))
            self.audit(user, 'plan.saved', plan_id)
            if request_id:
                self.db.execute('INSERT INTO plan_requests(user_id,request_id,project_id,request_hash,result) VALUES(?,?,?,?,?)',
                                (user['id'], request_id, project_id, fingerprint, canonical(result)))
            return result

    def delete_plan(self, user, project_id, data):
        from plan_deletions import delete
        with self.lock, self.db:
            return delete(self, user, project_id, 'plan', data)

    def plan_deletions(self, user, project_id):
        from plan_deletions import feed
        with self.lock:
            return feed(self, user, project_id)

    def draft(self, user, project_id, kind, description):
        self.require(user,("owner","manager","technician"))
        p = self.project(user,project_id)
        if kind not in ("Servicebericht","Lieferschein"):
            raise Problem(400,"Ungültiger Dokumenttyp")
        content = dict(project_id=p["id"],project_name=p["name"],customer=p["customer"],kind=kind,
                       description=text_field(description,"Beschreibung",10000),created_at=now_iso(),creator=user["id"])
        report = dict(id=uuid.uuid4().hex,content=content,content_hash=digest(canonical(content)),status="draft")
        with self.lock, self.db:
            self.db.execute("INSERT INTO reports(id,project_id,payload) VALUES(?,?,?)",(report["id"],project_id,canonical(report)))
            self.audit(user,"report.drafted",report["id"])
        return report

    def report(self, user, report_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM reports WHERE id=?",(report_id,)).fetchone()
            if not row:
                raise Problem(404,"Dokument nicht verfügbar")
            self.project(user,row["project_id"])
            return json.loads(row["payload"])

    def reports(self,user,project_id):
        self.project(user,project_id)
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM reports WHERE project_id=? ORDER BY rowid DESC",(project_id,))]

    def sign(self,user,report_id,expected_hash,signer,strokes):
        self.require(user,("owner","manager","technician"))
        signer = text_field(signer,"Name des Unterzeichners",200)
        if not isinstance(strokes,list) or not 1 <= len(strokes) <= 100:
            raise Problem(400,"Unterschrift fehlt")
        count=0
        for stroke in strokes:
            if not isinstance(stroke,list) or not 2 <= len(stroke) <= 2000:
                raise Problem(400,"Ungültige Unterschrift")
            count+=len(stroke)
            for point in stroke:
                if (not isinstance(point,list) or len(point)!=2 or
                    any(type(v) not in (int,float) or not 0<=v<=1 for v in point)):
                    raise Problem(400,"Ungültige Unterschrift")
        if count > 10000:
            raise Problem(400,"Unterschrift zu groß")
        with self.lock, self.db:
            r=self.report(user,report_id)
            if r["status"] != "draft":
                raise Problem(409,"Dokument bereits unterzeichnet")
            if expected_hash != r["content_hash"]:
                raise Problem(409,"Dokumentversion stimmt nicht überein")
            r.update(status="signed",signer=signer,strokes=strokes,signed_at=now_iso(),signed_by=user["id"])
            pdf=make_pdf(r)
            self.db.execute("UPDATE reports SET payload=?,pdf=?,pdf_hash=? WHERE id=?",
                            (canonical(r),pdf,hashlib.sha256(pdf).hexdigest(),report_id))
            self.audit(user,"report.signed",report_id)
            return r

    def pdf(self,user,report_id):
        r=self.report(user,report_id)
        with self.lock:
            row=self.db.execute("SELECT pdf,pdf_hash FROM reports WHERE id=?",(report_id,)).fetchone()
            if row["pdf"]:
                if hashlib.sha256(row["pdf"]).hexdigest()!=row["pdf_hash"]:
                    raise Problem(500,"Integritätsprüfung fehlgeschlagen")
                return bytes(row["pdf"])
        return make_pdf(r)

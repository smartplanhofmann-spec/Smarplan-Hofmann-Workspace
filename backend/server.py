import argparse
import getpass
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from core import Office, Problem, digest
from onedrive import OneDrive


def make_handler(office,drive):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # OAuth codes, passwords and tokens must not appear in request logs.

        def send(self,status,data,kind="application/json"):
            if kind=="application/json":
                data=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type",kind)
            self.send_header("Content-Length",str(len(data)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            if status == 405:
                self.send_header("Allow", self.allowed_methods)
            if kind == "application/pdf":
                self.send_header("Content-Disposition", 'inline; filename="smartplan-report.pdf"')
            self.end_headers()
            self.wfile.write(data)

        def dispatch(self):
            try:
                parsed=urllib.parse.urlsplit(self.path)
                path=parsed.path
                methods = {
                    "/health": "GET", "/api/login": "POST", "/oauth/callback": "GET",
                    "/api/me": "GET", "/api/logout": "POST", "/api/users": "GET, POST",
                    "/api/assignments": "POST", "/api/projects": "GET, POST",
                    "/api/storage/status": "GET", "/api/storage/connect": "POST",
                }
                self.allowed_methods = methods.get(path, "")
                if re.fullmatch(r"/api/users/[a-f0-9]{32}", path):
                    self.allowed_methods = "POST"
                if re.fullmatch(r"/api/projects/[a-f0-9]{32}/reports", path):
                    self.allowed_methods = "GET, POST"
                if re.fullmatch(r"/api/projects/[a-f0-9]{32}/assignments", path):
                    self.allowed_methods = "GET"
                if re.fullmatch(r"/api/reports/[a-f0-9]{32}(?:/pdf)?", path):
                    self.allowed_methods = "GET"
                if re.fullmatch(r"/api/reports/[a-f0-9]{32}/(?:sign|onedrive)", path):
                    self.allowed_methods = "POST"
                if self.allowed_methods and self.command not in self.allowed_methods.split(", "):
                    raise Problem(405, "HTTP-Methode nicht erlaubt")
                data={}
                if self.command=="POST":
                    size=int(self.headers.get("Content-Length","0"))
                    if not 0<size<=1000000:
                        raise Problem(413,"Anfrage zu groß oder leer")
                    data=json.loads(self.rfile.read(size))
                    if not isinstance(data,dict):
                        raise Problem(400,"JSON-Objekt erwartet")
                if path=="/health" and self.command=="GET":
                    return self.send(200,{"status":"ok","version":"0.2.0-development"})
                if path=="/api/login" and self.command=="POST":
                    return self.send(200,{"token":office.login(data.get("email"),data.get("password"))})
                if path=="/oauth/callback" and self.command=="GET":
                    q=urllib.parse.parse_qs(parsed.query)
                    drive.callback(q.get("state",[""])[0],q.get("code",[""])[0])
                    return self.send(200,"OneDrive verbunden. Du kannst dieses Fenster schließen.".encode(),"text/plain; charset=utf-8")
                auth=self.headers.get("Authorization","")
                if not auth.startswith("Bearer "):
                    raise Problem(401,"Bitte anmelden")
                user=office.user(auth[7:])
                if path=="/api/me" and self.command=="GET":
                    return self.send(200,user)
                if path=="/api/logout" and self.command=="POST":
                    with office.lock,office.db:
                        office.db.execute("DELETE FROM sessions WHERE token=?",(digest(auth[7:]),))
                    return self.send(200,{"ok":True})
                if path=="/api/users":
                    if self.command=="GET":
                        return self.send(200,office.users(user))
                    uid=office.create_user(user,data.get("email"),data.get("password"),data.get("role","technician"))
                    return self.send(201,{"id":uid})
                match=re.fullmatch(r"/api/users/([a-f0-9]{32})",path)
                if match:
                    return self.send(200,office.update_user(user,match[1],data))
                if path=="/api/assignments" and self.command=="POST":
                    office.assign(user,data.get("project_id"),data.get("user_id"),data.get("remove",False))
                    return self.send(200,{"ok":True})
                match=re.fullmatch(r"/api/projects/([a-f0-9]{32})/assignments",path)
                if match:
                    return self.send(200,office.assignments(user,match[1]))
                if path=="/api/projects":
                    if self.command=="GET":
                        return self.send(200,office.projects(user))
                    return self.send(201,{"id":office.add_project(user,data.get("name"),data.get("customer"))})
                match=re.fullmatch(r"/api/projects/([a-f0-9]{32})/reports",path)
                if match:
                    if self.command=="GET":
                        return self.send(200,office.reports(user,match[1]))
                    return self.send(201,office.draft(user,match[1],data.get("kind"),data.get("description")))
                match=re.fullmatch(r"/api/reports/([a-f0-9]{32})(?:/(sign|pdf|onedrive))?",path)
                if match:
                    rid,action=match.groups()
                    if action=="pdf" and self.command=="GET":
                        return self.send(200,office.pdf(user,rid),"application/pdf")
                    if action=="sign" and self.command=="POST":
                        return self.send(200,office.sign(user,rid,data.get("content_hash"),data.get("signer"),data.get("strokes")))
                    if action=="onedrive" and self.command=="POST":
                        return self.send(200,drive.upload_report(user,rid))
                    if not action and self.command=="GET":
                        return self.send(200,office.report(user,rid))
                if path=="/api/storage/status" and self.command=="GET":
                    office.require(user,("owner",))
                    return self.send(200,drive.status())
                if path=="/api/storage/connect" and self.command=="POST":
                    return self.send(200,{"url":drive.begin(user)})
                raise Problem(404,"Funktion nicht gefunden")
            except Problem as e:
                self.send(e.status,{"error":e.message})
            except (ValueError,TypeError,KeyError):
                self.send(400,{"error":"Ungültige Anfrage"})
            except Exception:
                self.send(500,{"error":"Interner Fehler"})

        do_GET=dispatch
        do_POST=dispatch
        do_PUT=dispatch
        do_PATCH=dispatch
        do_DELETE=dispatch
    return Handler


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--init-owner",metavar="EMAIL")
    parser.add_argument("--port",type=int,default=8765)
    args=parser.parse_args()
    data_dir=Path(os.getenv("OFFICE_DATA_DIR","data"))
    data_dir.mkdir(parents=True,exist_ok=True)
    office=Office(data_dir/"office.sqlite3")
    if args.init_owner:
        with office.lock:
            if office.db.execute("SELECT 1 FROM users WHERE role='owner'").fetchone():
                raise SystemExit("Geschäftsführung bereits angelegt")
        password=getpass.getpass("Neues Passwort (mindestens 12 Zeichen): ")
        if password!=getpass.getpass("Passwort wiederholen: "):
            raise SystemExit("Passwörter stimmen nicht überein")
        office.add_user(args.init_owner,password,"owner")
        print("Benutzer angelegt")
    else:
        print(f"Smartplan Office Entwicklungsserver: http://localhost:{args.port}")
        ThreadingHTTPServer(("127.0.0.1",args.port),make_handler(office,OneDrive(office))).serve_forever()

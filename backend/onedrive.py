"""Delegated personal OneDrive OAuth with PKCE and restricted app-folder storage."""
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from cryptography.fernet import Fernet
from core import Problem, canonical

GRAPH = "https://graph.microsoft.com/v1.0"
LOGIN = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
SCOPES = "offline_access Files.ReadWrite.AppFolder"


class OneDrive:
    def __init__(self, office):
        self.office = office
        self.client_id = os.getenv("MS_CLIENT_ID", "")
        self.secret = os.getenv("MS_CLIENT_SECRET", "")
        self.redirect = os.getenv("MS_REDIRECT_URI", "http://localhost:8765/oauth/callback")
        key = os.getenv("OFFICE_VAULT_KEY", "")
        self.vault = Fernet(key.encode()) if key else None
        self.pending = {}

    def configured(self):
        return bool(self.client_id and self.secret and self.vault)

    def status(self):
        with self.office.lock:
            connected = bool(self.office.db.execute("SELECT 1 FROM secrets WHERE name='onedrive' ").fetchone())
        return dict(configured=self.configured(), connected=connected, account_type="personal",scope=SCOPES)

    def begin(self, user):
        self.office.require(user,("owner",))
        if not self.configured():
            raise Problem(409,"Microsoft-App und verschlüsselter Tresor noch nicht konfiguriert")
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        with self.office.lock:
            self.pending = {s:v for s,v in self.pending.items() if v[2]>time.time()}
            self.pending[state]=(user["id"],verifier,time.time()+600)
        return LOGIN+"/authorize?"+urllib.parse.urlencode(dict(client_id=self.client_id,response_type="code",
            redirect_uri=self.redirect,response_mode="query",scope=SCOPES,state=state,
            code_challenge=challenge,code_challenge_method="S256",prompt="select_account"))

    def request(self,url,method="GET",data=None,headers=None):
        req=urllib.request.Request(url,data=data,headers=headers or {},method=method)
        try:
            with urllib.request.urlopen(req,timeout=30) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, ValueError):
            raise Problem(502,"OneDrive-Anfrage fehlgeschlagen; Verbindung oder Anmeldung prüfen")

    def token_request(self,data):
        data.update(client_id=self.client_id,client_secret=self.secret)
        return self.request(LOGIN+"/token","POST",urllib.parse.urlencode(data).encode(),
                            {"Content-Type":"application/x-www-form-urlencoded"})

    def save(self,tokens):
        tokens["expires_at"]=time.time()+int(tokens.get("expires_in",3600))
        encrypted=self.vault.encrypt(canonical(tokens).encode()).decode()
        with self.office.lock,self.office.db:
            self.office.db.execute("INSERT INTO secrets VALUES('onedrive',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(encrypted,))

    def callback(self,state,code):
        with self.office.lock:
            pending=self.pending.pop(state,None)
            if not pending or pending[2]<time.time():
                raise Problem(400,"Anmeldung abgelaufen oder bereits verwendet")
            row=self.office.db.execute("SELECT id,role,active FROM users WHERE id=?",(pending[0],)).fetchone()
            if not row or not row["active"] or row["role"]!="owner":
                raise Problem(403,"Berechtigung zur Verbindung fehlt")
        tokens=self.token_request(dict(grant_type="authorization_code",code=code,code_verifier=pending[1],
                                       redirect_uri=self.redirect,scope=SCOPES))
        self.save(tokens)
        with self.office.lock,self.office.db:
            self.office.audit(row,"onedrive.connected","personal")

    def access_token(self):
        if not self.configured():
            raise Problem(409,"OneDrive noch nicht konfiguriert")
        with self.office.lock:
            row=self.office.db.execute("SELECT value FROM secrets WHERE name='onedrive'").fetchone()
            if not row:
                raise Problem(409,"OneDrive noch nicht verbunden")
            tokens=json.loads(self.vault.decrypt(row[0].encode()))
            if tokens["expires_at"]<time.time()+60:
                updated=self.token_request(dict(grant_type="refresh_token",refresh_token=tokens["refresh_token"],scope=SCOPES))
                updated.setdefault("refresh_token",tokens["refresh_token"])
                self.save(updated)
                tokens=updated
            return tokens["access_token"]

    def upload_report(self,user,report_id):
        self.office.require(user,("owner","manager"))
        report=self.office.report(user,report_id)
        if report["status"]!="signed":
            raise Problem(409,"Zunächst Dokument unterzeichnen")
        data=self.office.pdf(user,report_id)
        token=self.access_token()
        headers={"Authorization":"Bearer "+token}
        folder=self.request(GRAPH+"/me/drive/special/approot",headers=headers)
        name=report["content"]["project_id"]+"_"+report_id+".pdf"
        url=GRAPH+"/me/drive/items/"+urllib.parse.quote(folder["id"],safe="")+":/"+name+":/content"
        result=self.request(url,"PUT",data,{**headers,"Content-Type":"application/pdf"})
        with self.office.lock,self.office.db:
            self.office.db.execute("UPDATE reports SET onedrive_id=? WHERE id=?",(result["id"],report_id))
            self.office.audit(user,"onedrive.uploaded",report_id)
        # No public sharing URL: access continues through Office permissions.
        return dict(uploaded=True,item_id=result["id"])

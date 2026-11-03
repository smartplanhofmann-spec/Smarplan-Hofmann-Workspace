"""Operator-only preparation of a fixed, separate company installation.

No HTTP tenant selector, shared customer database, implicit adoption or public
activation. Pure plans and root-owned receipts are separate from secrets.
"""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
from types import SimpleNamespace

from core import canonical
from online.instance_roles import InstanceRoles,SLUG,HEX,_unique


FORMAT=1
HOST=re.compile(r'(?=.{3,253}\Z)[a-z0-9]+(?:[.-][a-z0-9]+)+')
COMMIT=re.compile(r'[a-f0-9]{40}')
ROOTS={'code':'/opt/smartplan-companies','config':'/etc/smartplan-companies',
       'state':'/var/lib/smartplan-companies','operator':'/var/lib/smartplan-company-operator'}


@dataclass(frozen=True)
class Company:
    slug:str
    instance_id:str
    public_host:str
    port:int
    source_commit:str
    privacy_installation_id:str
    plan_import:bool=False

    def __post_init__(self):
        if (not isinstance(self.slug,str) or not SLUG.fullmatch(self.slug)
                or not isinstance(self.instance_id,str) or not HEX.fullmatch(self.instance_id)
                or not isinstance(self.privacy_installation_id,str) or not HEX.fullmatch(self.privacy_installation_id)
                or self.privacy_installation_id==self.instance_id
                or not isinstance(self.public_host,str) or not HOST.fullmatch(self.public_host)
                or self.public_host in ('office.smartplan-hofmann.de','localhost')
                or any(len(part)>63 or part.startswith('-') or part.endswith('-') for part in self.public_host.split('.'))
                or type(self.port) is not int or not 1024<=self.port<=65535 or self.port in (5432,8765,8766)
                or not isinstance(self.source_commit,str) or not COMMIT.fullmatch(self.source_commit)
                or type(self.plan_import) is not bool):
            raise ValueError('Ungültiges oder mit dem Bestandsbetrieb kollidierendes Unternehmensmanifest.')

    @property
    def roles(self):return InstanceRoles.company(self.slug,self.instance_id)

    def document(self):return dict(schema=FORMAT,**self.__dict__)

    @property
    def sha256(self):return hashlib.sha256(canonical(self.document()).encode()).hexdigest()

    def paths(self):
        values={key:root+'/'+self.slug for key,root in ROOTS.items()}
        values['release']=values['code']+'/releases/'+self.source_commit
        values['documents']=values['state']+'/documents'
        values['backups']=values['state']+'/backups'
        values['privacy']=values['state']+'/privacy'
        return values


def parse(value):
    if not isinstance(value,dict) or set(value)!={'schema',*Company.__dataclass_fields__} or type(value['schema']) is not int or value['schema']!=FORMAT:
        raise ValueError('Vollständiges versioniertes Unternehmensmanifest erforderlich.')
    return Company(**{key:item for key,item in value.items() if key!='schema'})


def read_manifest(path,*,protected=False):
    path=Path(path)
    if protected:_safe_parents(path,uid=0)
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as source:
        info=os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or not 0<info.st_size<=8192
                or protected and (info.st_uid!=0 or info.st_mode & 0o022)):
            raise ValueError('Reguläres, begrenztes Betreibermanifest erforderlich.')
        raw=source.read(8193)
        after=os.fstat(source.fileno())
        if len(raw)!=info.st_size or (info.st_size,info.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError('Manifest wurde während des Lesens verändert.')
    return parse(json.loads(raw,object_pairs_hook=_unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Ungültige JSON-Zahl.'))))


def check_inventory(company,others):
    for other in others:
        if type(other) is not Company:raise ValueError('Geprüftes Unternehmensinventar erforderlich.')
        if company.document()==other.document():continue
        keys=('slug','instance_id','public_host','port','privacy_installation_id')
        if any(getattr(company,key)==getattr(other,key) for key in keys):
            raise ValueError('Unternehmensressource ist bereits anders reserviert.')
    return True


def plan(company,others=()):
    check_inventory(company,others)
    return dict(schema=FORMAT,manifest=company.document(),manifest_sha256=company.sha256,
        roles=company.roles.document(),paths=company.paths(),
        units=['smartplan-'+company.slug+'-'+name for name in ('api.service','backup.service','backup.timer','import.service')],
        phases=['reserved','files_prepared','database_prepared','instance_bound','runtime_verified','loopback_accepted'],
        public_activation=False,external_delivery_enabled=False,existing_installation_modified=False)


def render(company):
    """Deterministic non-secret configuration; all service paths are derived."""
    paths=company.paths();roles=company.roles
    from psycopg.conninfo import make_conninfo
    environment=dict(SMARTPLAN_DATABASE_DSN=make_conninfo(dbname=roles.database,user=roles.runtime,host='/var/run/postgresql'),
        SMARTPLAN_INSTANCE_ID=company.instance_id,SMARTPLAN_PUBLIC_HOST=company.public_host,
        SMARTPLAN_INSTANCE_ROLES_FILE=paths['config']+'/instance-roles.json',
        SMARTPLAN_VAULT_KEY_FILE=paths['state']+'/vault.key',SMARTPLAN_STORAGE_CONFIG_FILE=paths['config']+'/storage.json',
        SMARTPLAN_PRIVACY_CHECKPOINT_FILE=paths['privacy']+'/checkpoint.json',
        SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE=paths['privacy']+'/key',SMARTPLAN_PRIVACY_INSTALLATION_ID=company.privacy_installation_id)
    common=f'''User={roles.linux_user}
Group={roles.linux_user}
WorkingDirectory={paths['release']}/app/backend
EnvironmentFile={paths['config']}/service.env
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
CapabilityBoundingSet=
ReadWritePaths={paths['state']}
TasksMax=128
'''
    python=paths['release']+'/venv/bin/python'
    units={
        'api.service':f'''[Unit]
Description=Smartplan company {company.slug} private API
After=postgresql.service
[Service]
Type=exec
{common}ExecStartPre={python} -m online.provisioning runtime-check --manifest {paths['config']}/manifest.json
ExecStart={paths['release']}/venv/bin/gunicorn online.web:create_app() --bind 127.0.0.1:{company.port} --workers 2 --threads 4 --worker-class gthread --timeout 240 --graceful-timeout 15 --forwarded-allow-ips 127.0.0.1
Restart=on-failure
RestartSec=5
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
[Install]
WantedBy=multi-user.target
''',
        'backup.service':f'''[Unit]
Description=Smartplan company {company.slug} private backup
After=postgresql.service
[Service]
Type=oneshot
{common}ExecStart={python} -m online.provisioning backup --manifest {paths['config']}/manifest.json
RestrictAddressFamilies=AF_UNIX
TimeoutStartSec=330
''',
        'backup.timer':f'''[Unit]
Description=Smartplan company {company.slug} backup schedule
[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=900
Unit=smartplan-{company.slug}-backup.service
[Install]
WantedBy=timers.target
''',
        'import.service':f'''[Unit]
Description=Smartplan company {company.slug} isolated plan import
After=postgresql.service
[Service]
Type=exec
{common}ExecStartPre={python} -m online.provisioning runtime-check --manifest {paths['config']}/manifest.json
ExecStart={python} -m online.import_worker --worker-python {paths['release']}/plan-import/bin/python --ocr-languages deu+eng --watch
Restart=on-failure
RestartSec=30
RestrictAddressFamilies=AF_UNIX AF_NETLINK
KillMode=control-group
TimeoutStopSec=20
MemoryMax=1536M
MemorySwapMax=0
CPUQuota=150%
LimitFSIZE=32M
LimitCORE=0
[Install]
WantedBy=multi-user.target
'''}
    # A fragment is reviewed and installed separately; no shared Caddyfile is changed.
    proxy=f'''{company.public_host} {{
  header {{
    -Server
    X-Content-Type-Options nosniff
    Referrer-Policy no-referrer
    X-Robots-Tag "noindex, nofollow"
    Cache-Control no-store
    Strict-Transport-Security "max-age=31536000"
  }}
  @browser path / /office /office/*
  header @browser >Content-Security-Policy "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
  @online path /api/v1/* /health /ready / /office /office/*
  handle @online {{
    reverse_proxy 127.0.0.1:{company.port} {{
      transport http {{
        dial_timeout 3s
        response_header_timeout 240s
      }}
    }}
  }}
  handle {{ respond "Nicht gefunden" 404 }}
}}
'''
    files={'manifest.json':canonical(company.document())+'\n','instance-roles.json':canonical(roles.document())+'\n',
        'storage.json':canonical({'server':{'path':paths['documents']}})+'\n',
        'service.env':''.join(key+'='+shlex.quote(value)+'\n' for key,value in environment.items()),'Caddyfile.fragment':proxy}
    files.update({'smartplan-'+company.slug+'-'+name:value for name,value in units.items()})
    return {name:value.encode() for name,value in files.items()}


def _exclusive(path,data,mode=0o600):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as target:
        os.fchmod(target.fileno(),mode)
        target.write(data);target.flush();os.fsync(target.fileno())


def _private_directory(path,uid=None,*,trusted_root=None):
    path=Path(path);uid=os.geteuid() if uid is None else uid
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=uid or info.st_mode & 0o077:
        raise ValueError('Privates eigenes Betreiberverzeichnis erforderlich.')
    _safe_parents(path,uid=uid,trusted_root=trusted_root)
    return path


def _safe_parents(path,*,uid,trusted_root=None):
    if not path.is_absolute():raise ValueError('Absoluter Betreiberpfad erforderlich.')
    if trusted_root is not None:
        trusted_root=Path(trusted_root)
        if path!=trusted_root and trusted_root not in path.parents:raise ValueError('Pfad außerhalb injizierter Testwurzel.')
        info=trusted_root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=uid or info.st_mode & 0o077:raise ValueError('Testwurzel ist nicht privat.')
        if path==trusted_root:return
    for parent in path.parents:
        info=parent.lstat()
        # Non-root synthetic workspace under the system sticky temporary root.
        temporary=(uid!=0 and parent==Path('/tmp') and info.st_uid==0 and info.st_mode & stat.S_ISVTX)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0,uid)
                or info.st_mode & 0o022 and not temporary):
            raise ValueError('Betreiberpfad hat veränderliche oder fremde Eltern.')
        if parent==trusted_root:break


@contextmanager
def reservation(directory,company,*,trusted_root=None):
    """Exact reservation, serialized retries; no best-effort adoption."""
    directory=_private_directory(directory,trusted_root=trusted_root)
    fd=os.open(directory/'.provision.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.geteuid() or info.st_mode & 0o077:
            raise ValueError('Unsichere Betreibersperre.')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest=directory/'reservation.json'
        raw=canonical(company.document()).encode()
        if manifest.exists() or manifest.is_symlink():
            saved=read_manifest(manifest)
            if saved.document()!=company.document():raise ValueError('Reservierung gehört einem anderen Auftrag.')
        else:_exclusive(manifest,raw)
        yield directory
    finally:os.close(fd)


def write_bundle(directory,company,others=(),*,trusted_root=None):
    check_inventory(company,others)
    with reservation(directory,company,trusted_root=trusted_root) as root:
        files=render(company)
        for name,raw in files.items():
            destination=root/name
            if destination.exists() or destination.is_symlink():
                info=destination.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode & 0o077 or destination.read_bytes()!=raw:
                    raise ValueError('Vorhandenes Vorbereitungsartefakt weicht ab; nicht überschrieben.')
            else:_exclusive(destination,raw)
        value=dict(manifest_sha256=company.sha256,files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},
            phase='files_prepared',secrets_created=False,public_activation=False)
        raw=canonical(value).encode();destination=root/'bundle.json'
        if destination.exists():
            if destination.is_symlink() or destination.read_bytes()!=raw:raise ValueError('Bundlequittung weicht ab.')
        else:_exclusive(destination,raw)
        return value


def _operator_dsn(company,dsn,*,test_mode=False):
    """Strict trusted operator selector; no service files or SQL options."""
    from psycopg.conninfo import conninfo_to_dict,make_conninfo
    value=conninfo_to_dict(dsn)
    allowed={'host','port','user','dbname','connect_timeout'}|({'password'} if test_mode else set())
    if set(value)-allowed or value.get('user')!='postgres':raise ValueError('Expliziter lokaler PostgreSQL-Operator erforderlich.')
    if test_mode:
        if value.get('host') not in ('127.0.0.1','localhost') or value.get('dbname')!='smartplan_check' or value.get('port')!='55433':
            raise ValueError('Provisionierungstest ausschließlich im reservierten Einwegcluster 55433.')
        if not company.slug.startswith('test'):raise ValueError('Synthetischer Instanzname erforderlich.')
    else:
        import pwd
        if (os.geteuid()!=pwd.getpwnam('postgres').pw_uid or value.get('host')!='/var/run/postgresql'
                or value.get('port','5432')!='5432' or value.get('dbname')!='postgres'
                or any(os.environ.get(k) for k in ('PGHOSTADDR','PGPORT','PGSERVICE','PGSERVICEFILE','PGOPTIONS'))):
            raise ValueError('Geschützter PostgreSQL-Peer-Operatorpfad erforderlich.')
    return make_conninfo(dsn,dbname=company.roles.database)


def prepare_database(company,admin_dsn,*,test_mode=False,runtime_password=None):
    """Create only receipt-bound new roles/database; exact retries verify them."""
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from online.store import migrate
    from online.release import secure_database,no_other_clients
    roles=company.roles;target=_operator_dsn(company,admin_dsn,test_mode=test_mode)
    if runtime_password is not None and (not test_mode or not isinstance(runtime_password,str) or not 16<=len(runtime_password)<=128):
        raise ValueError('Produktionsrollen benutzen Peer-Anmeldung, keine Passwortparameter.')
    receipt='smartplan-provision-v1:'+company.sha256
    with psycopg.connect(admin_dsn,connect_timeout=5) as admin:
        admin.execute('SELECT pg_advisory_xact_lock(741290519)')
        for name,login in ((roles.runtime,True),(roles.owner,False)):
            row=admin.execute("SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname=%s",(name,)).fetchone()
            if row is None:
                admin.execute(sql.SQL('CREATE ROLE {} {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(name),sql.SQL('LOGIN' if login else 'NOLOGIN')))
                admin.execute(sql.SQL('COMMENT ON ROLE {} IS {}').format(sql.Identifier(name),sql.Literal(receipt)))
                if login and runtime_password is not None:
                    admin.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(name),sql.Literal(runtime_password)))
            elif row!=(login,False,False,False,False,False,receipt):
                raise ValueError('Vorhandene Rolle gehört nicht exakt zu dieser Vorbereitung.')
            if admin.execute("SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s)",(name,)).fetchone():
                raise ValueError('Vorhandene Rolle besitzt unerwartete Mitgliedschaften.')
    # CREATE DATABASE cannot share a transaction with its receipt. A crash in
    # that narrow gap deliberately needs operator review, never blind adoption.
    with psycopg.connect(admin_dsn,connect_timeout=5,autocommit=True) as admin:
        row=admin.execute("SELECT pg_get_userbyid(datdba),shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",(roles.database,)).fetchone()
        if row is None:
            admin.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(roles.database),sql.Identifier(roles.owner)))
            admin.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(roles.database),sql.Literal(receipt)))
            admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(roles.database)))
        elif row!=(roles.owner,receipt):raise ValueError('Vorhandene Datenbank darf nicht übernommen werden.')
    no_other_clients(target)
    migrate(target,owner_role=roles.owner,compatibility_mode='business',require_business_modules=True,instance_roles=roles)
    security_dsn=target if test_mode else make_conninfo(target,user=roles.runtime)
    secure_database(security_dsn,test_mode=test_mode,instance_roles=roles)
    return dict(instance_id=company.instance_id,manifest_sha256=company.sha256,phase='database_prepared',public_activation=False)


def initial_bind(company,admin_dsn,binder,*,test_mode=False):
    """One scoped INSERT grant, always revoked, before any service activation.

    binder is a trusted operator callback which runs the existing bind operation
    under the company's runtime OS identity. No privileged credentials or vault
    bytes are passed to the callback by this function.
    """
    import psycopg
    from psycopg import sql
    from online.store import PostgresOffice
    from online.instance_roles import verify_database
    roles=company.roles;target=_operator_dsn(company,admin_dsn,test_mode=test_mode)
    with psycopg.connect(target,connect_timeout=5,autocommit=True) as admin:
        admin.execute('SELECT pg_advisory_lock(741290519)')
        try:
            receipt=admin.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
            if receipt!='smartplan-provision-v1:'+company.sha256:raise ValueError('Datenbankvorbereitung nicht nachgewiesen.')
            admin.execute(sql.SQL('REVOKE INSERT ON business_instance_identity FROM {}').format(sql.Identifier(roles.runtime)))
            if admin.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND backend_type='client backend' AND pid<>pg_backend_pid()").fetchone():
                raise ValueError('Erstbindung benötigt vollständig gestoppte neue Dienste.')
            row=admin.execute('SELECT instance_id FROM business_instance_identity').fetchone()
            if row is not None and row[0]!=company.instance_id:raise ValueError('Fremde Instanzbindung.')
            if row is None:
                admin.execute(sql.SQL('GRANT INSERT ON business_instance_identity TO {}').format(sql.Identifier(roles.runtime)))
            try:
                binder()
            finally:
                admin.execute(sql.SQL('REVOKE INSERT ON business_instance_identity FROM {}').format(sql.Identifier(roles.runtime)))
            office=PostgresOffice(target,instance_roles=roles)
            try:verify_database(office,require_bound=True)
            finally:office.db.close()
            if admin.execute("SELECT has_any_column_privilege(%s,'business_instance_identity','INSERT')",(roles.runtime,)).fetchone()[0]:
                raise ValueError('Temporäre Bindungsrechte wurden nicht vollständig entzogen.')
        finally:admin.execute('SELECT pg_advisory_unlock(741290519)')
    return dict(instance_id=company.instance_id,phase='instance_bound',temporary_insert_revoked=True,public_activation=False)


def runtime_check(company,*,office=None,key=None,storage=None):
    """Check actual role, binding and independent privacy checkpoint read-only."""
    from online.store import PostgresOffice
    from online.instance import verify
    from online.storage import Storage
    from online.instance_roles import for_office
    from business_schema import require_runtime_security,privacy_restore_guard
    own=office is None
    if own:office=PostgresOffice(os.environ['SMARTPLAN_DATABASE_DSN'])
    try:
        if for_office(office)!=company.roles:raise ValueError('Laufzeitrollen gehören nicht zur Instanz.')
        require_runtime_security(office)
        if key is None:key=Path(os.environ['SMARTPLAN_VAULT_KEY_FILE']).read_bytes().strip()
        if storage is None:storage=Storage(office,key,company.public_host)
        verify(office,company.instance_id,company.public_host,key,storage)
        # Guard validates external HMAC and replay. A successful normal startup
        # never substitutes a newly empty checkpoint for an existing history.
        with office.lock,office.db:privacy_restore_guard(office)
        return dict(instance_id=company.instance_id,manifest_sha256=company.sha256,
                    runtime_verified=True,owner_initialized=bool(office.db.execute("SELECT 1 FROM users WHERE active=1 AND role='owner'").fetchone()),public_activation=False)
    finally:
        if own:office.db.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('plan','bundle','runtime-check','backup'))
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--directory')
    parser.add_argument('--inventory',action='append',default=[])
    args=parser.parse_args(argv)
    try:
        company=read_manifest(args.manifest,protected=args.action in ('runtime-check','backup'))
        others=[read_manifest(path) for path in args.inventory]
        if args.action=='plan':result=plan(company,others)
        elif args.action=='bundle':
            if not args.directory:raise ValueError('Eigenes privates Vorbereitungsverzeichnis erforderlich.')
            result=write_bundle(args.directory,company,others)
        else:
            result=runtime_check(company)
            if args.action=='backup':
                from online.backup import backup
                backup(os.environ['SMARTPLAN_DATABASE_DSN'],company.paths()['backups'])
                result={**result,'backup_created':True}
        print(canonical(result))
    except Exception:
        # Driver exceptions may contain DSNs or internal credential paths.
        raise SystemExit('Unternehmensvorbereitung fehlgeschlagen; Manifest, eigene Ressourcen und geschützte Konfiguration prüfen. Keine öffentliche Freigabe.') from None


if __name__=='__main__':main()

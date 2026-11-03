"""Explicit local operator CLI for a previously prepared, pinned company release.

Only called by an operator, never HTTP. Public proxy configuration is rendered
but never installed. Existing installation scripts are deliberately separate.
"""
import argparse
import fcntl
import grp
import json
import os
from pathlib import Path
import pwd
import shlex
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request

from core import canonical
from online import provisioning as p
from online.release import atomic_write

ADMIN_DSN='host=/var/run/postgresql dbname=postgres user=postgres'


def _run(command,*,environment=None,input=None,capture=True):
    environment=environment if environment is not None else {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8'}
    result=subprocess.run(command,env=environment,input=input,stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,timeout=330)
    if result.returncode:raise ValueError('Geschützter Betreiberschritt fehlgeschlagen; keine öffentliche Freigabe.')
    return result.stdout


def _directory(path,uid,gid,mode):
    path=Path(path);p._safe_parents(path,uid=0)
    if not path.exists() and not path.is_symlink():
        path.mkdir(mode=mode);os.chown(path,uid,gid);path.chmod(mode)
    info=path.lstat()
    if not stat.S_ISDIR(info.st_mode) or (info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode))!=(uid,gid,mode):
        raise ValueError('Vorhandenes Verzeichnis hat fremde Eigentümer oder Rechte.')


def _release(company):
    paths=company.paths();root=Path(paths['release'])
    p._safe_parents(root,uid=0)
    protected_tree(root)
    for path in (root,root/'app',root/'app/backend',root/'app/web',root/'venv',root/'venv/bin'):
        info=path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:
            raise ValueError('Vorbereiteter unveränderlicher Release fehlt.')
    for path in (root/'SOURCE_COMMIT',root/'app/backend/online/provisioning_host.py',root/'app/backend/online/provisioning.py'):
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:
            raise ValueError('Betreiber-Code muss root gehören.')
    if (root/'SOURCE_COMMIT').read_text().strip()!=company.source_commit:
        raise ValueError('Vorbereiteter Quellstand stimmt nicht mit dem Manifest überein.')
    python=(root/'venv/bin/python').resolve(strict=True)
    p._safe_parents(python,uid=0)
    info=python.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022 or not os.access(python,os.X_OK):
        raise ValueError('Geschützter vorbereiteter Pythonruntime fehlt.')
    return str(root/'venv/bin/python')


def protected_tree(root,*,expected_uid=0,trusted_root=None):
    """The complete executable tree, including dependencies, must be immutable."""
    root=Path(root);p._safe_parents(root,uid=expected_uid,trusted_root=trusted_root)
    count=0
    for directory,children,files in os.walk(root,followlinks=False):
        for path in [Path(directory),*(Path(directory)/name for name in children+files)]:
            count+=1
            if count>200000:raise ValueError('Vorbereiteter Runtimebaum überschreitet die Prüfgrenze.')
            info=path.lstat()
            if info.st_uid!=expected_uid:raise ValueError('Code-/Runtimebaum hat fremde Eigentümer.')
            if stat.S_ISLNK(info.st_mode):
                target=path.resolve(strict=True);p._safe_parents(target,uid=expected_uid,trusted_root=trusted_root if target.is_relative_to(root) else None)
                info=target.stat()
                if stat.S_ISDIR(info.st_mode) and not target.is_relative_to(root):
                    raise ValueError('Externe Verzeichnislinks im Runtimebaum sind gesperrt.')
            if (not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))
                    or info.st_uid!=expected_uid or info.st_mode & 0o022):
                raise ValueError('Code-/Runtimebaum ist beschreibbar oder enthält unerwartete Dateien.')


def _environment(company):
    lines=p.render(company)['service.env'].decode().splitlines()
    values={key:shlex.split(value)[0] for key,value in (line.split('=',1) for line in lines)}
    return {'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','PYTHONNOUSERSITE':'1','PYTHONSAFEPATH':'1',
        'PYTHONPATH':company.paths()['release']+'/app/backend',**values}


def _child(company,action,*,runtime=False,extra=(),interactive=False):
    python=_release(company);user=company.roles.linux_user if runtime else 'postgres'
    command=['runuser','-u',user,'--',python,'-m','online.provisioning_host',action,
             '--manifest',company.paths()['config']+'/manifest.json',*extra]
    # postgres cannot traverse runtime-private storage/config. Its manifest is
    # passed over stdin from this root verifier, with no secret values.
    if not runtime:command=['runuser','-u','postgres','--',python,'-m','online.provisioning_host',action,'--operator-stdin']
    return _run(command,environment=_environment(company),
        input=None if runtime else canonical(company.document()).encode(),capture=not interactive)


def _config_file(path,raw,gid):
    path=Path(path)
    if path.exists() or path.is_symlink():
        info=path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_gid!=gid
                or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o640 or path.read_bytes()!=raw):
            raise ValueError('Geschützte Konfiguration weicht ab; nicht überschrieben.')
    else:
        p._exclusive(path,raw,0o640);os.chown(path,0,gid)


def _account(company):
    roles=company.roles;home=company.paths()['state'];comment='Smartplan company '+company.instance_id
    try:account=pwd.getpwnam(roles.linux_user)
    except KeyError:
        try:grp.getgrnam(roles.linux_user)
        except KeyError:pass
        else:raise ValueError('Fremde vorhandene Dienstgruppe nicht übernehmen.')
        _run(['useradd','--system','--user-group','--no-create-home','--home-dir',home,
              '--shell','/usr/sbin/nologin','--comment',comment,roles.linux_user])
        account=pwd.getpwnam(roles.linux_user)
    if (account.pw_uid==0 or account.pw_dir!=home or account.pw_gecos!=comment
            or account.pw_shell!='/usr/sbin/nologin'
            or grp.getgrgid(account.pw_gid).gr_name!=roles.linux_user
            or set(os.getgrouplist(roles.linux_user,account.pw_gid))!={account.pw_gid}):
        raise ValueError('Dienstkonto ist nicht exakt dieser Instanz zugeordnet.')
    return account


def _state(path,value):
    atomic_write(path,canonical(value).encode(),mode=0o600,uid=0,gid=0)


def _runtime_secrets(company):
    """Runtime UID only, exact retry; private keys never reach postgres."""
    from cryptography.fernet import Fernet
    from online.instance_roles import configured
    roles=company.roles
    if configured()!=roles or os.geteuid()!=pwd.getpwnam(roles.linux_user).pw_uid:
        raise ValueError('Geheimer Initialisierungsschritt benötigt die eigene Runtime-Identität.')
    paths=company.paths();receipt=Path(paths['state'])/'.secret-fingerprints.json'
    import hashlib
    files={Path(paths['state'])/'vault.key':Fernet.generate_key,
           Path(paths['privacy'])/'key':lambda:os.urandom(32)}
    existing=None
    if receipt.exists() or receipt.is_symlink():
        info=receipt.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode & 0o077:
            raise ValueError('Private Schlüsselquittung ist nicht geschützt.')
        existing=json.loads(receipt.read_bytes(),object_pairs_hook=p._unique)
    fingerprints={}
    for path,generate in files.items():
        if not path.exists() and not path.is_symlink():
            if existing is not None:raise ValueError('Bestätigter Schlüssel fehlt; nicht neu erzeugen.')
            p._exclusive(path,generate(),0o400)
        with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as source:
            info=os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o400 or info.st_size>128:
                raise ValueError('Privater Schlüsselbestand ist ungültig.')
            raw=source.read(129)
        if path.name=='vault.key':Fernet(raw)
        elif len(raw)!=32:raise ValueError('Ungültiger Checkpointschlüssel.')
        fingerprints[path.name]=hashlib.sha256(raw).hexdigest()
    value=dict(manifest_sha256=company.sha256,keys=fingerprints)
    if existing is not None and existing!=value:raise ValueError('Private Schlüssel wurden verändert.')
    if existing is None:p._exclusive(receipt,canonical(value).encode())


def binding_permission(company,enabled):
    """Trusted postgres phase; root holds the installation lock across phases."""
    import psycopg
    from psycopg import sql
    target=p._operator_dsn(company,ADMIN_DSN)
    with psycopg.connect(target,autocommit=True) as db:
        receipt=db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        if receipt!='smartplan-provision-v1:'+company.sha256:raise ValueError('Datenbankreservation fehlt.')
        db.execute(sql.SQL('REVOKE INSERT ON business_instance_identity FROM {}').format(sql.Identifier(company.roles.runtime)))
        if enabled:
            from online.release import no_other_clients
            active=db.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND backend_type='client backend' AND pid<>pg_backend_pid()").fetchone()
            if active:raise ValueError('Neue Instanz hat aktive Datenbanknutzer.')
            identity=db.execute('SELECT instance_id FROM business_instance_identity').fetchone()
            if identity is None:db.execute(sql.SQL('GRANT INSERT ON business_instance_identity TO {}').format(sql.Identifier(company.roles.runtime)))
            elif identity[0]!=company.instance_id:raise ValueError('Fremde Instanzbindung.')


def prepare(company):
    if os.geteuid()!=0:raise ValueError('Hostvorbereitung benötigt einen ausdrücklichen lokalen Root-Betreiber.')
    _release(company)
    for path in p.ROOTS.values():_directory(path,0,0,0o755 if path!=p.ROOTS['operator'] else 0o700)
    root=Path(p.ROOTS['operator']);lock=os.open(root/'inventory.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        others=[]
        for child in root.iterdir():
            if child.name=='inventory.lock':continue
            if child.is_symlink() or not child.is_dir():raise ValueError('Unbekannter Eintrag im Betreiberinventar.')
            if (child/'reservation.json').exists():others.append(p.read_manifest(child/'reservation.json',protected=True))
            elif child.name!=company.slug:raise ValueError('Unvollständige fremde Ressourcenreservation.')
        p.check_inventory(company,others)
        journal=root/company.slug
        if not journal.exists():journal.mkdir(mode=0o700)
        p.write_bundle(journal,company,others)
        # Refuse modifying a running installation; use check for live inspection.
        for unit in p.plan(company)['units']:
            status=_run(['systemctl','show',unit,'--property=ActiveState','--value']).decode().strip()
            if status not in ('inactive','failed',''):raise ValueError('Vorbereitung benötigt gestoppte eigene Units.')
        account=_account(company);paths=company.paths()
        _directory(paths['config'],0,account.pw_gid,0o750)
        _directory(paths['state'],account.pw_uid,account.pw_gid,0o700)
        # Runtime-owned parents are traversed only by that runtime for private children.
        for name in ('manifest.json','instance-roles.json','storage.json','service.env'):
            _config_file(Path(paths['config'])/name,p.render(company)[name],account.pw_gid)
        _child(company,'runtime-directories',runtime=True)
        _child(company,'runtime-secrets',runtime=True)
        _child(company,'db-prepare')
        bind_company(company)
        _child(company,'runtime-privacy',runtime=True)
        _child(company,'runtime-check',runtime=True)
        for name,raw in p.render(company).items():
            if name.endswith(('.service','.timer')):
                target=Path('/etc/systemd/system')/name
                if target.exists() or target.is_symlink():
                    info=target.lstat()
                    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022 or target.read_bytes()!=raw:
                        raise ValueError('Vorhandene Unit ist nicht exakt dieser Instanz zugeordnet.')
                else:p._exclusive(target,raw,0o644)
        _run(['systemctl','daemon-reload'])
        _state(journal/'host-state.json',dict(manifest_sha256=company.sha256,phase='private_prepared',public_activation=False))
        return dict(phase='private_prepared',owner_setup_required=True,public_activation=False)
    finally:os.close(lock)


def bind_company(company):
    try:
        _child(company,'bind-grant')
        _child(company,'runtime-bind',runtime=True)
    finally:_child(company,'bind-revoke')


def runtime_action(company,action,owner_email=None):
    from online.instance_roles import configured
    if configured()!=company.roles or os.geteuid()!=pwd.getpwnam(company.roles.linux_user).pw_uid:
        raise ValueError('Nur die eigene Runtime darf diesen Schritt ausführen.')
    paths=company.paths()
    if action=='runtime-directories':
        for name in ('documents','backups','privacy'):
            path=Path(paths[name])
            if not path.exists():path.mkdir(mode=0o700)
            info=path.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode & 0o077:
                raise ValueError('Private Runtime-Ablage ist fremd oder unsicher.')
    elif action=='runtime-secrets':_runtime_secrets(company)
    elif action=='runtime-bind':
        from online.instance import main
        main(['bind'])
    elif action=='runtime-privacy':
        from online.store import PostgresOffice
        from business_schema import initialize_privacy_checkpoint,privacy_restore_guard
        office=PostgresOffice(os.environ['SMARTPLAN_DATABASE_DSN'])
        try:
            with office.lock,office.db:
                if office.db.execute('SELECT 1 FROM business_privacy_anchors').fetchone():privacy_restore_guard(office)
                else:initialize_privacy_checkpoint(office)
        finally:office.db.close()
    elif action=='runtime-owner':
        if not owner_email:raise ValueError('Explizite Owner-E-Mail erforderlich.')
        _run([sys.executable,'-m','online.manage','init-owner',owner_email],environment=_environment(company),capture=False)
    else:return p.runtime_check(company)
    return dict(completed=action,public_activation=False)


def start_private(company):
    """Start only this reviewed private instance; never reload the public proxy."""
    if os.geteuid()!=0:raise ValueError('Expliziter lokaler Root-Betreiber erforderlich.')
    _release(company)
    journal=Path(company.paths()['operator']);p._private_directory(journal,uid=0)
    with inventory_lock(company),p.reservation(journal,company):
        saved=json.loads((journal/'host-state.json').read_bytes(),object_pairs_hook=p._unique)
        if saved.get('manifest_sha256')!=company.sha256 or saved.get('phase') not in ('private_prepared','loopback_accepted'):
            raise ValueError('Vollständige private Vorbereitung fehlt.')
        proof=json.loads(_child(company,'runtime-check',runtime=True))
        if proof.get('runtime_verified') is not True or proof.get('owner_initialized') is not True:
            raise ValueError('Eigener geprüfter Owner muss zuerst angelegt werden.')
        for name,raw in p.render(company).items():
            if not name.endswith(('.service','.timer')):continue
            path=Path('/etc/systemd/system')/name;info=path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022 or path.read_bytes()!=raw:
                raise ValueError('Die eigene Unit stimmt nicht mit dem vorbereiteten Manifest überein.')
            for property_ in ('DropInPaths','Environment'):
                if _run(['systemctl','show',name,'--property='+property_,'--value']).strip():
                    raise ValueError('Versteckte Unit-Overrides verhindern eine Freigabe.')
        if company.plan_import:
            python=_release(company)
            _run(['runuser','-u',company.roles.linux_user,'--',python,'-m','online.import_worker',
                '--worker-python',company.paths()['release']+'/plan-import/bin/python','--ocr-languages','deu+eng','--doctor'],environment=_environment(company))
        api='smartplan-'+company.slug+'-api.service';started=[]
        try:
            already_active=_run(['systemctl','show',api,'--property=ActiveState','--value']).decode().strip()=='active'
            if already_active:verify_listener(api,company.port)
            else:
                with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
                    probe.bind(('127.0.0.1',company.port))
            def start(unit):
                active=_run(['systemctl','show',unit,'--property=ActiveState','--value']).decode().strip()=='active'
                if not active:started.append(unit)
                _run(['systemctl','start',unit])
            start(api)
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            ready=False
            for _ in range(10):
                request=urllib.request.Request('http://127.0.0.1:'+str(company.port)+'/ready',
                    headers={'Host':company.public_host,'X-Forwarded-Proto':'https'})
                try:
                    with opener.open(request,timeout=3) as response:
                        value=json.loads(response.read(8192))
                    ready=value.get('status')=='ok' and value.get('database')=='ok'
                except (OSError,ValueError):pass
                if ready:break
                time.sleep(0.5)
            if not ready:raise ValueError('Eigene Loopback-Bereitschaft fehlt.')
            verify_listener(api,company.port)
            request=urllib.request.Request('http://127.0.0.1:'+str(company.port)+'/api/v1/projects',
                headers={'Host':company.public_host,'X-Forwarded-Proto':'https'})
            try:
                with opener.open(request,timeout=3) as response:status=response.status
            except urllib.error.HTTPError as response:status=response.code
            if status!=401:raise ValueError('Ungeschützter eigener Projektzugriff wurde nicht gesperrt.')
            start('smartplan-'+company.slug+'-backup.service')
            start('smartplan-'+company.slug+'-backup.timer')
            if company.plan_import:start('smartplan-'+company.slug+'-import.service')
            verify_listener(api,company.port)
            result=dict(manifest_sha256=company.sha256,phase='loopback_accepted',public_activation=False)
            _state(journal/'host-state.json',result)
            return result
        except BaseException:
            for unit in reversed(started):
                try:_run(['systemctl','stop',unit])
                except Exception:pass
            raise


def verify_listener(unit,port):
    active=_run(['systemctl','show',unit,'--property=ActiveState','--value']).decode().strip()
    pid_text=_run(['systemctl','show',unit,'--property=MainPID','--value']).decode().strip()
    if active!='active' or not pid_text.isdecimal() or int(pid_text)<2:
        raise ValueError('Die eigene API-Unit ist nicht dauerhaft aktiv.')
    directory=Path('/proc')/pid_text
    descriptors=set()
    for item in (directory/'fd').iterdir():
        try:value=os.readlink(item)
        except FileNotFoundError:continue
        if value.startswith('socket:[') and value.endswith(']'):descriptors.add(value[8:-1])
    expected='0100007F:'+format(port,'04X')
    for line in (directory/'net/tcp').read_text().splitlines()[1:]:
        fields=line.split()
        if len(fields)>9 and fields[1]==expected and fields[3]=='0A' and fields[9] in descriptors:return
    raise ValueError('Der geprüfte Loopback-Port gehört nicht zur eigenen API-Unit.')


@p.contextmanager
def inventory_lock(company):
    root=Path(company.paths()['operator']).parent;p._private_directory(root,uid=0)
    descriptor=os.open(root/'inventory.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1 or info.st_mode & 0o077:
            raise ValueError('Betreiberinventarsperre ist nicht geschützt.')
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(descriptor)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','check','init-owner','start-private','db-prepare','bind-grant','bind-revoke',
        'runtime-directories','runtime-secrets','runtime-bind','runtime-privacy','runtime-check','runtime-owner'))
    parser.add_argument('--manifest');parser.add_argument('--operator-stdin',action='store_true')
    parser.add_argument('--owner-email')
    args=parser.parse_args(argv)
    try:
        if args.operator_stdin:
            if args.action not in ('db-prepare','bind-grant','bind-revoke') or os.geteuid()!=pwd.getpwnam('postgres').pw_uid:
                raise ValueError('Nur geschützter PostgreSQL-Operator darf den internen Phasenweg nutzen.')
            company=p.parse(json.loads(sys.stdin.buffer.read(8193),object_pairs_hook=p._unique))
        else:
            if not args.manifest:raise ValueError('Geschütztes Manifest erforderlich.')
            company=p.read_manifest(args.manifest,protected=True)
        if args.action=='prepare':result=prepare(company)
        elif args.action=='start-private':result=start_private(company)
        elif args.action in ('check','init-owner'):
            if os.geteuid()!=0:raise ValueError('Expliziter Root-Betreiber erforderlich.')
            with inventory_lock(company):
                _child(company,'runtime-owner' if args.action=='init-owner' else 'runtime-check',runtime=True,
                    extra=('--owner-email',args.owner_email) if args.owner_email else (),interactive=args.action=='init-owner')
            result=dict(completed=args.action,public_activation=False)
        elif args.action=='db-prepare':result=p.prepare_database(company,ADMIN_DSN)
        elif args.action in ('bind-grant','bind-revoke'):
            binding_permission(company,args.action=='bind-grant');result=dict(completed=args.action,public_activation=False)
        else:result=runtime_action(company,args.action,args.owner_email)
        print(canonical(result))
    except Exception:
        raise SystemExit('Unternehmensvorbereitung gesperrt; geschützte Ressourcen und Phasen prüfen. Keine öffentliche Aktivierung.') from None


if __name__=='__main__':main()

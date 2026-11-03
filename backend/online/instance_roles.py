"""Immutable process configuration for separately provisioned PostgreSQL roles.

Never select a company from an HTTP value or infer authorization from a DSN.
Legacy installations retain their exact established role names.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat


SLUG = re.compile(r'[a-z][a-z0-9]{2,23}')
HEX = re.compile(r'[a-f0-9]{32}')


@dataclass(frozen=True)
class InstanceRoles:
    runtime: str = 'smartplan-online'
    owner: str = 'smartplan-migrator'
    linux_user: str = 'smartplan-online'
    slug: str | None = None
    instance_id: str | None = None

    def __post_init__(self):
        if self.slug is None:
            if (self.runtime,self.owner,self.linux_user,self.instance_id) != (
                    'smartplan-online','smartplan-migrator','smartplan-online',None):
                raise ValueError('Unbekannte Legacy-Rollenbeschreibung.')
        elif (not isinstance(self.slug,str) or not SLUG.fullmatch(self.slug)
                or not isinstance(self.instance_id,str) or not HEX.fullmatch(self.instance_id)
                or (self.runtime,self.owner,self.linux_user) != (
                    'sp_'+self.slug+'_run','sp_'+self.slug+'_own','sp_'+self.slug+'_run')):
            raise ValueError('Ungültige feste Unternehmensrollen.')

    @classmethod
    def company(cls,slug,instance_id):
        return cls('sp_'+slug+'_run','sp_'+slug+'_own','sp_'+slug+'_run',slug,instance_id)

    @property
    def database(self):
        return 'smartplan_online' if self.slug is None else 'sp_'+self.slug

    def owns_database_name(self,value):
        return isinstance(value,str) and (value==self.database or
            self.slug is not None and value.startswith(self.database+'_') and
            re.fullmatch(r'[a-z][a-z0-9_]{1,62}',value) is not None)

    def document(self):
        if self.slug is None:raise ValueError('Legacy-Konfiguration benötigt keine neue Datei.')
        return dict(schema=1,slug=self.slug,instance_id=self.instance_id,
            runtime=self.runtime,owner=self.owner,linux_user=self.linux_user)


LEGACY = InstanceRoles()


def parse(value):
    if (not isinstance(value,dict) or set(value)!={'schema','slug','instance_id','runtime','owner','linux_user'}
            or type(value['schema']) is not int or value['schema']!=1):
        raise ValueError('Exakte Unternehmensrollenbeschreibung erforderlich.')
    return InstanceRoles(**{k:v for k,v in value.items() if k!='schema'})


def _unique(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('Mehrdeutige Betreiberkonfiguration.')
        value[key]=item
    return value


def load(path,*,expected_uid=0,trusted_root=None):
    """Read-only protected file; expected_uid is for injected local fixtures."""
    candidate=Path(path)
    if not candidate.is_absolute():raise ValueError('Absoluter Betreiberpfad erforderlich.')
    if trusted_root is not None:
        trusted_root=Path(trusted_root)
        if candidate==trusted_root or trusted_root not in candidate.parents:
            raise ValueError('Testdatei außerhalb der ausdrücklich injizierten Trust-Root.')
    for parent in candidate.parents:
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=expected_uid or info.st_mode & 0o022:
            raise ValueError('Rollenpfad muss vom Betreiber unveränderlich verwahrt werden.')
        if parent==trusted_root:break
    with os.fdopen(os.open(candidate,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
        info=os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=expected_uid
                or info.st_mode & 0o022 or not 0<info.st_size<=4096):
            raise ValueError('Geschützte reguläre Rollenbeschreibung erforderlich.')
        raw=stream.read(4097)
        after=os.fstat(stream.fileno())
        if len(raw)!=info.st_size or (after.st_mtime_ns,after.st_size)!=(info.st_mtime_ns,info.st_size):
            raise ValueError('Rollenbeschreibung wurde während des Lesens verändert.')
    return parse(json.loads(raw,object_pairs_hook=_unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Ungültige JSON-Zahl.'))))


def configured():
    path=os.environ.get('SMARTPLAN_INSTANCE_ROLES_FILE')
    if path is None:return LEGACY
    roles=load(path)
    if os.environ.get('SMARTPLAN_INSTANCE_ID')!=roles.instance_id:
        raise ValueError('Rollenbeschreibung ist nicht an die Prozessinstanz gebunden.')
    return roles


def for_office(office=None):
    roles=getattr(office,'instance_roles',None) if office is not None else None
    if roles is None:roles=configured()
    if type(roles) is not InstanceRoles:raise ValueError('Vertrauenswürdige feste Rollenbeschreibung erforderlich.')
    return roles


def verify_database(office,*,require_bound=False):
    roles=for_office(office)
    if roles.slug is None:return
    actual=office.db.execute('SELECT current_database()').fetchone()[0]
    if not roles.owns_database_name(actual):
        raise ValueError('Verbindung gehört nicht zum festen Unternehmensbereich.')
    from online.instance import identity
    saved=identity(office)
    if (saved is None and require_bound or saved is not None and saved['instance_id']!=roles.instance_id):
        raise ValueError('Datenbankidentität gehört nicht zur festen Unternehmensinstanz.')

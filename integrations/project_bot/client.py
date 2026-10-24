#!/usr/bin/env python3
"""Optional stdlib transport for an existing bot's read-only metadata jobs.

No provider account is opened by this helper. The bot owns provider read tools
and its durable, immutable result ledger. Output never contains account data.
"""
import argparse
from datetime import datetime, date
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit


JOBS_URL = 'https://office.smartplan-hofmann.de/api/v1/intake/integrations/jobs'
MAX_BYTES = 2 * 1024 * 1024
PROVIDERS = ('google_calendar','onedrive')
ERROR_CODES = ('provider_unavailable','reconnect_required','rate_limited','timeout',
               'invalid_response','not_found','permission_denied','unsupported','resource_too_large')
_ID = re.compile(r'[a-f0-9]{32}\Z')


class DeliveryError(Exception):
    def __init__(self, code, *, http_status=None, retry_after=None):
        super().__init__(code)
        self.code, self.http_status, self.retry_after = code, http_status, retry_after


def _pairs(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise DeliveryError('INVALID_JSON')
        result[key]=value
    return result


def _constant(_):
    raise DeliveryError('INVALID_JSON')


def _parse(raw):
    try:
        result = json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_constant)
        _tree(result)
        return result
    except (ValueError,UnicodeError,RecursionError):
        raise DeliveryError('INVALID_JSON') from None


def _tree(value):
    pending, count = [(value,0)],0
    while pending:
        item,depth = pending.pop()
        if depth>20:
            raise DeliveryError('INVALID_METADATA')
        if isinstance(item,dict):
            for key,child in item.items():
                if (not isinstance(key,str) or not key or len(key)>200 or
                        key.casefold() in {'access_token','refresh_token','client_secret','api_token','authorization',
                                           'credential','config','downloadurl','@microsoft.graph.downloadurl'}):
                    raise DeliveryError('UNSAFE_METADATA')
                pending.append((child,depth+1))
        elif isinstance(item,list):
            count+=len(item)
            if count>10000:
                raise DeliveryError('TOO_MANY_ITEMS')
            pending.extend((child,depth+1) for child in item)
        elif isinstance(item,float) and not math.isfinite(item):
            raise DeliveryError('INVALID_METADATA')
        elif item is not None and type(item) not in (str,int,float,bool):
            raise DeliveryError('INVALID_METADATA')


def _encode(value):
    _tree(value)
    try:
        raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    except (ValueError,UnicodeError,TypeError,RecursionError):
        raise DeliveryError('INVALID_JSON') from None
    if len(raw)>MAX_BYTES:
        raise DeliveryError('METADATA_TOO_LARGE')
    return raw


def _opaque(value,maximum=2048):
    if not isinstance(value,str) or not 1<=len(value)<=maximum or not value.strip() or not value.isprintable():
        raise DeliveryError('INVALID_METADATA')
    return value


def _id(value):
    if not isinstance(value,str) or not _ID.fullmatch(value):
        raise DeliveryError('INVALID_JOB_ID')
    return value


def _positive(value):
    if type(value) is not int or not 1<=value<=2147483647:
        raise DeliveryError('INVALID_JOB')
    return value


def validate_jobs(value):
    if (not isinstance(value,dict) or set(value)!={'providers','jobs'} or
            not isinstance(value['providers'],list) or not 1<=len(value['providers'])<=2 or
            any(not isinstance(provider,str) or provider not in PROVIDERS for provider in value['providers']) or
            len(value['providers'])!=len(set(value['providers'])) or not isinstance(value['jobs'],list) or len(value['jobs'])>100):
        raise DeliveryError('INVALID_JOB_LIST')
    seen=set()
    allowed={'id','provider','kind','generation','requested_generation','resource','selection','project_id','revision','expires_at'}
    required={'id','provider','kind','generation','resource','selection'}
    for job in value['jobs']:
        if not isinstance(job,dict) or not required<=set(job) or set(job)-allowed:
            raise DeliveryError('INVALID_JOB')
        identifier=_id(job['id'])
        if identifier in seen:
            raise DeliveryError('DUPLICATE_JOB')
        seen.add(identifier)
        _positive(job['generation'])
        if 'requested_generation' in job:
            _positive(job['requested_generation'])
        if job['provider'] not in value['providers'] or job['kind'] not in ('catalog','resource','snapshot') or not isinstance(job['selection'],dict):
            raise DeliveryError('INVALID_JOB')
        if job.get('project_id') is not None:
            _id(job['project_id'])
        if job.get('revision') is not None:
            _positive(job['revision'])
        if job['kind']=='catalog':
            if job['resource'] is not None or job['selection'] or job.get('project_id') is not None:
                raise DeliveryError('INVALID_JOB')
        else:
            _opaque(job['resource'])
            if job['provider']=='onedrive':
                resource=_parse(job['resource'].encode('utf-8'))
                if not isinstance(resource,dict) or set(resource)!={'drive_id','folder_id'}:
                    raise DeliveryError('INVALID_JOB')
                for identifier in resource.values():
                    _opaque(identifier)
        if job['kind']=='snapshot':
            _id(job.get('project_id'));_positive(job.get('revision'))
            selection=job['selection']
            if job['provider']=='google_calendar':
                if (set(selection)!={'calendar_id','event_ids'} or selection['calendar_id']!=job['resource'] or
                        not isinstance(selection['event_ids'],list) or len(selection['event_ids'])>50):
                    raise DeliveryError('INVALID_JOB')
                ids=[_opaque(item) for item in selection['event_ids']]
                if len(ids)!=len(set(ids)):
                    raise DeliveryError('INVALID_JOB')
            elif selection!=resource:
                raise DeliveryError('INVALID_JOB')
        if 'expires_at' in job:
            stamp=job['expires_at']
            if type(stamp) in (int,float):
                if not math.isfinite(stamp) or stamp<=0:
                    raise DeliveryError('INVALID_JOB')
            elif isinstance(stamp,str):
                try:
                    if datetime.fromisoformat(stamp.replace('Z','+00:00')).tzinfo is None:
                        raise ValueError()
                except ValueError:
                    raise DeliveryError('INVALID_JOB') from None
            else:
                raise DeliveryError('INVALID_JOB')
    _encode(value)
    return value


def validate_result(value):
    if not isinstance(value,dict):
        raise DeliveryError('INVALID_RESULT')
    _tree(value)
    _id(value.get('job_id'));_opaque(value.get('source_id'),200)
    if 'error_code' in value:
        if set(value)!={'job_id','source_id','error_code'} or value['error_code'] not in ERROR_CODES:
            raise DeliveryError('INVALID_RESULT')
    else:
        if set(value)!={'job_id','source_id','complete','payload'} or value['complete'] is not True:
            raise DeliveryError('INCOMPLETE_RESULT')
        payload=value['payload']
        shapes=[{'complete','identity','calendars'},{'complete','identity','folders'},
                {'complete','calendar','events'},{'complete','folder','files'}]
        if not isinstance(payload,dict) or set(payload) not in shapes or payload.get('complete') is not True:
            raise DeliveryError('INCOMPLETE_RESULT')
        main,items=(('identity','calendars') if 'calendars' in payload else
                    ('identity','folders') if 'folders' in payload else
                    ('calendar','events') if 'events' in payload else ('folder','files'))
        if not isinstance(payload[main],dict) or not isinstance(payload[items],list) or len(payload[items])>1000:
            raise DeliveryError('INVALID_METADATA')
        _opaque(payload[main].get('id'))
        if main=='identity':
            _opaque(payload[main].get('label'),500)
        if main=='folder':
            _opaque(payload['folder'].get('drive_id'));_opaque(payload['folder'].get('name'),500)
            if not isinstance(payload['folder'].get('path'),str) or len(payload['folder']['path'])>4096:
                raise DeliveryError('INVALID_METADATA')
            if 'url' in payload['folder']:_opaque(payload['folder']['url'],8192)
            _web_url(payload['folder'].get('url'),'onedrive')
        if items in ('calendars','events'):
            _google(payload,items)
        seen=set()
        for item in payload[items]:
            if not isinstance(item,dict):
                raise DeliveryError('INVALID_METADATA')
            identifier=_opaque(item.get('id'))
            if items in ('files','folders'):
                _opaque(item.get('drive_id'))
                _opaque(item.get('name'),500)
                if not isinstance(item.get('path'),str) or len(item['path'])>4096:
                    raise DeliveryError('INVALID_METADATA')
                if 'url' in item:_opaque(item['url'],8192)
                _web_url(item.get('url'),'onedrive')
            identity=(item.get('drive_id'),identifier) if items in ('files','folders') else identifier
            if identity in seen:
                raise DeliveryError('DUPLICATE_ITEM')
            seen.add(identity)
            if items=='files':
                _opaque(item.get('url'),8192);_opaque(item.get('media_type'),200)
                expected_path=payload['folder']['path'].rstrip('/')+'/'+item['name']
                if (item['drive_id']!=payload['folder'].get('drive_id') or item.get('parent_id')!=payload['folder']['id'] or
                        type(item.get('size')) is not int or item['size']<0 or item['path']!=expected_path or
                        '/' in item['name'] or '\\' in item['name'] or item['name'] in ('.','..')):
                    raise DeliveryError('INVALID_FOLDER_MEMBERSHIP')
                _opaque(item.get('rev'))
    body={key:item for key,item in value.items() if key!='job_id'}
    _encode(body)
    return body


def _web_url(value,provider):
    if value is None:return
    try:
        parsed=urlsplit(value)
        host=parsed.hostname or ''
        allowed=(host in ('calendar.google.com','www.google.com') and parsed.path.startswith('/calendar/')) if provider=='google_calendar' else (host=='onedrive.live.com' or host.endswith('.sharepoint.com'))
        valid=(isinstance(value,str) and len(value)<=8192 and allowed and parsed.scheme=='https' and
               parsed.username is None and parsed.password is None and parsed.port in (None,443) and
               not any(ord(char)<33 or ord(char)>126 for char in value))
    except (ValueError,TypeError,AttributeError):
        valid=False
    if not valid:raise DeliveryError('UNSAFE_METADATA_URL')


def _google(payload,items):
    calendars=payload['calendars'] if items=='calendars' else [payload['calendar']]
    for calendar in calendars:
        if not isinstance(calendar,dict):raise DeliveryError('INVALID_METADATA')
        _opaque(calendar.get('id'));_opaque(calendar.get('name'),2048)
        if calendar.get('time_zone') is not None:_opaque(calendar['time_zone'],128)
    if items=='calendars':return
    if len(payload['events'])>500:raise DeliveryError('TOO_MANY_ITEMS')
    for event in payload['events']:
        if not isinstance(event,dict):raise DeliveryError('INVALID_METADATA')
        status=event.get('status')
        if status in ('cancelled','not_found'):
            if any(event.get(key) is not None for key in ('start','end','all_day')):
                raise DeliveryError('INVALID_EVENT_TIME')
        elif status in ('confirmed','tentative'):
            try:
                if type(event.get('all_day')) is not bool:raise ValueError()
                if event['all_day']:
                    if any(not isinstance(event.get(key),str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',event[key]) for key in ('start','end')):raise ValueError()
                    first,last=(date.fromisoformat(event[key]) for key in ('start','end'))
                else:
                    first,last=(datetime.fromisoformat(event[key].replace('Z','+00:00')) for key in ('start','end'))
                    if first.tzinfo is None or last.tzinfo is None:raise ValueError()
                if last<=first:raise ValueError()
            except (KeyError,TypeError,ValueError,AttributeError,OverflowError):
                raise DeliveryError('INVALID_EVENT_TIME') from None
            _opaque(event.get('title'),2048)
            for key,maximum in (('description',32768),('location',2048)):
                if event.get(key) is not None and (not isinstance(event[key],str) or len(event[key])>maximum):
                    raise DeliveryError('INVALID_METADATA')
        else:raise DeliveryError('INVALID_METADATA')
        if event.get('time_zone') is not None:_opaque(event['time_zone'],128)
        _web_url(event.get('url'),'google_calendar')


def stable_source_id(payload):
    """Use only for a fully captured immutable payload, never retry timestamps."""
    return hashlib.sha256(_encode(payload)).hexdigest()


def _private_read(filename,maximum):
    descriptor=None
    try:
        path=Path(filename)
        if path.is_symlink():
            raise DeliveryError('UNSAFE_PRIVATE_FILE')
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        info=os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or (os.name=='posix' and (info.st_mode&0o077 or info.st_uid!=os.geteuid()))):
            raise DeliveryError('UNSAFE_PRIVATE_FILE')
        with os.fdopen(descriptor,'rb') as stream:
            descriptor=None
            raw=stream.read(maximum+1)
        if len(raw)>maximum:
            raise DeliveryError('PRIVATE_FILE_TOO_LARGE')
        return raw
    except OSError:
        raise DeliveryError('PRIVATE_FILE_UNREADABLE') from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def load_token(filename=None):
    value=os.environ.get('SMARTPLAN_INTEGRATION_TOKEN','')
    if filename and value:
        raise DeliveryError('USE_ONE_CREDENTIAL_SOURCE')
    if filename:
        try:
            value=_private_read(filename,200).decode('utf-8')
        except UnicodeError:
            raise DeliveryError('INVALID_CREDENTIAL') from None
    return header_credential(value.strip())


def header_credential(value):
    # A protected platform handle is opaque. urllib cannot resolve a placeholder;
    # a native authenticated HTTPS action must bind the actual value on the wire.
    if not isinstance(value,str) or not 1<=len(value)<=193 or any(not 33<=ord(c)<=126 for c in value):
        raise DeliveryError('INVALID_CREDENTIAL')
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def _request(url,token,*,body=None,opener=None):
    token=header_credential(token)
    headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
    if body is not None:
        headers['Content-Type']='application/json'
    request=urllib.request.Request(url,data=body,method='POST' if body is not None else 'GET',headers=headers)
    limit=4096 if body is not None else MAX_BYTES
    try:
        with (opener or urllib.request.build_opener(NoRedirect())).open(request,timeout=20) as response:
            expected=201 if body is not None else 200
            if response.status!=expected:
                raise DeliveryError('UNEXPECTED_HTTP_STATUS',http_status=response.status)
            if response.headers.get('Content-Type','').split(';',1)[0].strip().lower()!='application/json':
                raise DeliveryError('UNCONFIRMED_RESPONSE')
            raw=response.read(limit+1)
    except urllib.error.HTTPError as error:
        status=error.code
        retry=error.headers.get('Retry-After','') if error.headers else ''
        retry=int(retry) if re.fullmatch(r'[0-9]{1,5}',retry) and int(retry)<=86400 else None
        error.close()
        raise DeliveryError('HTTP_FAILURE',http_status=status,retry_after=retry) from None
    except (urllib.error.URLError,OSError,TimeoutError,http.client.HTTPException):
        raise DeliveryError('NETWORK_UNCONFIRMED') from None
    if len(raw)>limit:
        raise DeliveryError('UNCONFIRMED_RESPONSE')
    return _parse(raw)


def list_jobs(token,*,opener=None):
    return validate_jobs(_request(JOBS_URL,token,opener=opener))


def send_result(value,token,*,opener=None):
    body=validate_result(value)
    receipt=_request(JOBS_URL+'/'+value['job_id']+'/result',token,body=_encode(body),opener=opener)
    if (not isinstance(receipt,dict) or set(receipt)!={'status','job_id','idempotent'} or
            receipt.get('status')!='received' or receipt.get('job_id')!=value['job_id'] or type(receipt.get('idempotent')) is not bool):
        raise DeliveryError('UNCONFIRMED_RECEIPT')
    return receipt


def write_jobs(filename,value):
    raw=_encode(validate_jobs(value))
    descriptor=None
    try:
        descriptor=os.open(filename,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(descriptor,'wb') as stream:
            descriptor=None
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
    except OSError:
        raise DeliveryError('PRIVATE_OUTPUT_NOT_CREATED') from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


class SafeParser(argparse.ArgumentParser):
    def error(self,_):
        self.exit(2,'{"status":"unconfirmed","error":"INVALID_ARGUMENTS"}\n')


def main(argv=None):
    parser=SafeParser(description=__doc__,allow_abbrev=False)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--list-jobs',action='store_true')
    action.add_argument('--result')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--send',action='store_true')
    mode.add_argument('--check',action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--token-file')
    args=parser.parse_args(argv)
    try:
        if args.list_jobs:
            if not args.send or not args.output:
                raise DeliveryError('INVALID_ARGUMENTS')
            jobs=list_jobs(load_token(args.token_file));write_jobs(args.output,jobs)
            output={'status':'jobs_saved','count':len(jobs['jobs'])}
        else:
            if args.output:
                raise DeliveryError('INVALID_ARGUMENTS')
            result=_parse(_private_read(args.result,MAX_BYTES))
            validate_result(result)
            output={'status':'checked'} if args.check else send_result(result,load_token(args.token_file))
        print(json.dumps(output,separators=(',',':')))
        return 0
    except DeliveryError as error:
        output={'status':'unconfirmed','error':error.code}
        if error.http_status is not None:output['http_status']=error.http_status
        if error.retry_after is not None:output['retry_after']=error.retry_after
        print(json.dumps(output,separators=(',',':')))
        return 1


if __name__=='__main__':
    sys.exit(main())

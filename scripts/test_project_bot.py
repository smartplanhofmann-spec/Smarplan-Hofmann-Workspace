"""Portable client/ZIP tests. Provider IO and backend imports are absent."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import importlib.util
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import zipfile
import hashlib


ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'integrations'/'project_bot'


def load(name):
    spec=importlib.util.spec_from_file_location('smartplan_project_bot_'+name,DIRECTORY/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


client=load('client')
packager=load('package')
JOB='1'*32
TOKEN='opaque-protected-handle-synthetic'


def result():
    return json.loads((DIRECTORY/'examples/catalog_result.json').read_text(encoding='utf-8'))


def jobs():
    return {'providers':['google_calendar','onedrive'],'jobs':[{
        'id':JOB,'provider':'google_calendar','kind':'catalog','generation':1,'requested_generation':1,
        'resource':None,'selection':{},'project_id':None,'revision':None,'expires_at':2000000000.0}]}


class Response(BytesIO):
    def __init__(self,value,*,status=200,media_type='application/json',raw=False):
        super().__init__(value if raw else json.dumps(value).encode('utf-8'))
        self.status=status;self.headers={'Content-Type':media_type}


class Opener:
    def __init__(self,*responses):
        self.responses=list(responses);self.requests=[]

    def open(self,request,*,timeout):
        self.requests.append((request,timeout))
        item=self.responses.pop(0)
        if isinstance(item,Exception):raise item
        return item


class ProjectBotTests(unittest.TestCase):
    def error(self,code,callback):
        with self.assertRaises(client.DeliveryError) as caught:callback()
        self.assertEqual(code,caught.exception.code)
        return caught.exception

    def test_get_jobs_fixed_host_scopes_and_private_output(self):
        opener=Opener(Response(jobs()))
        value=client.list_jobs(TOKEN,opener=opener)
        request,timeout=opener.requests[0]
        self.assertEqual(client.JOBS_URL,request.full_url)
        self.assertEqual('GET',request.method)
        self.assertEqual('Bearer '+TOKEN,request.get_header('Authorization'))
        self.assertEqual(20,timeout)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'jobs.json';client.write_jobs(path,value)
            self.assertEqual(value,json.loads(path.read_text(encoding='utf-8')))
            if os.name=='posix':self.assertEqual(0,path.stat().st_mode&0o077)
            self.error('PRIVATE_OUTPUT_NOT_CREATED',lambda:client.write_jobs(path,value))

    def test_single_remaining_provider_is_usable_after_other_scope_disconnect(self):
        value=jobs();value['providers']=['google_calendar']
        self.assertEqual(value,client.validate_jobs(value))
        value['jobs'][0]['provider']='onedrive'
        self.error('INVALID_JOB',lambda:client.validate_jobs(value))

    def test_invalid_alias_duplicate_job_snapshot_and_untrusted_job_fields_fail(self):
        for mutation in [lambda x:x['providers'].append('dropbox'),
                         lambda x:x['jobs'].append(deepcopy(x['jobs'][0])),
                         lambda x:x['jobs'][0].update(script='fetch this unknown URL'),
                         lambda x:x['jobs'][0].update(kind='snapshot')]:
            value=jobs();mutation(value)
            with self.assertRaises(client.DeliveryError):client.validate_jobs(value)

    def test_result_exact_retries_preserve_body_and_only_confirm_matching_receipt(self):
        value=result()
        opener=Opener(Response({'status':'received','job_id':JOB,'idempotent':False},status=201),
                      Response({'status':'received','job_id':JOB,'idempotent':True},status=201))
        self.assertFalse(client.send_result(value,TOKEN,opener=opener)['idempotent'])
        self.assertTrue(client.send_result(value,TOKEN,opener=opener)['idempotent'])
        first,second=[request for request,_ in opener.requests]
        self.assertEqual(client.JOBS_URL+'/'+JOB+'/result',first.full_url)
        self.assertEqual(first.data,second.data)
        self.assertNotIn('job_id',json.loads(first.data))
        self.assertEqual(value['source_id'],json.loads(first.data)['source_id'])
        self.assertNotIn(TOKEN,first.full_url)
        for receipt in [{'status':'received','job_id':'2'*32,'idempotent':False},
                        {'status':'received','job_id':JOB,'idempotent':1}, {'status':'queued','job_id':JOB,'idempotent':False}]:
            self.error('UNCONFIRMED_RECEIPT',lambda:client.send_result(value,TOKEN,opener=Opener(Response(receipt,status=201))))

    def test_unconfirmed_network_http_and_redirect_are_sanitized_without_autoretry(self):
        for response,code in [(URLError(TOKEN),'NETWORK_UNCONFIRMED'),
                              (HTTPError('https://secret.invalid/'+TOKEN,401,TOKEN,{},BytesIO(TOKEN.encode())),'HTTP_FAILURE'),
                              (HTTPError('https://secret.invalid/'+TOKEN,302,TOKEN,{'Location':'https://evil.invalid'},BytesIO()),'HTTP_FAILURE')]:
            opener=Opener(response)
            error=self.error(code,lambda:client.send_result(result(),TOKEN,opener=opener))
            self.assertNotIn(TOKEN,str(error));self.assertEqual(1,len(opener.requests))
        self.assertIsNone(client.NoRedirect().redirect_request(None,None,302,'',{},'https://evil.invalid'))

    def test_rate_limit_exposes_only_bounded_numeric_wait(self):
        for header,expected in [('300',300),(TOKEN,None),('999999999999999',None)]:
            error=HTTPError(client.JOBS_URL,429,TOKEN,{'Retry-After':header},BytesIO(TOKEN.encode()))
            caught=self.error('HTTP_FAILURE',lambda:client.list_jobs(TOKEN,opener=Opener(error)))
            self.assertEqual(expected,caught.retry_after)

    def test_incomplete_oversized_credential_containing_and_bad_json_are_rejected(self):
        for change in [lambda x:x.update(complete=False),lambda x:x['payload'].update(complete=False),
                       lambda x:x['payload'].update(refresh_token='private'),lambda x:x['payload']['calendars'].append(deepcopy(x['payload']['calendars'][0]))]:
            value=result();change(value)
            with self.assertRaises(client.DeliveryError):client.validate_result(value)
        for raw in [b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e999}',b'\xff']:
            with self.assertRaises(client.DeliveryError):client._parse(raw)
        value=result();value['payload']['calendars']=[{'id':'synthetic-'+str(i)+'q'*100,'name':'x'*2048,'time_zone':'Europe/Berlin'} for i in range(1000)]
        self.error('METADATA_TOO_LARGE',lambda:client.validate_result(value))
        self.error('UNCONFIRMED_RESPONSE',lambda:client.list_jobs(TOKEN,opener=Opener(Response(b'x'*(client.MAX_BYTES+1),raw=True))))

    def test_onedrive_direct_membership_and_no_temporary_download_urls(self):
        value={'job_id':JOB,'source_id':'synthetic-rev','complete':True,'payload':{'complete':True,
            'folder':{'id':'folder','drive_id':'drive','name':'Synthetic folder','path':'/'},
            'files':[{'id':'file','drive_id':'drive','parent_id':'folder','name':'plan.pdf','path':'/plan.pdf',
                      'rev':'etag-1','size':10,'media_type':'application/pdf','url':'https://example.sharepoint.com/sites/site/plan.pdf'}]}}
        client.validate_result(value)
        value['payload']['files'][0]['parent_id']='different-folder'
        self.error('INVALID_FOLDER_MEMBERSHIP',lambda:client.validate_result(value))
        value['payload']['files'][0]['parent_id']='folder'
        value['payload']['files'][0]['@microsoft.graph.downloadUrl']='https://download.invalid'
        self.error('UNSAFE_METADATA',lambda:client.validate_result(value))

    def test_normalized_google_examples_preserve_offsets_all_day_end_and_tombstones(self):
        for name in ('catalog_result.json','google_resource_result.json','onedrive_catalog_result.json','onedrive_resource_result.json'):
            value=json.loads((DIRECTORY/'examples'/name).read_text(encoding='utf-8'))
            client.validate_result(value)
        value=json.loads((DIRECTORY/'examples/google_resource_result.json').read_text(encoding='utf-8'))
        event=value['payload']['events'][0]
        event.update(start='2030-06-12',end='2030-06-13',all_day=True)
        client.validate_result(value)
        event['end']='2030-06-12'
        self.error('INVALID_EVENT_TIME',lambda:client.validate_result(value))
        event.update(start='2030-06-12T09:00:00',end='2030-06-12T10:00:00',all_day=False)
        self.error('INVALID_EVENT_TIME',lambda:client.validate_result(value))
        event.clear();event.update(id='removed-event',status='cancelled',start=None,end=None,all_day=None)
        client.validate_result(value)

    def test_fixed_failure_envelope_is_delivered_without_fake_empty_success(self):
        value=json.loads((DIRECTORY/'examples/error_result.json').read_text(encoding='utf-8'))
        self.assertEqual({'source_id':value['source_id'],'error_code':'unsupported'},client.validate_result(value))
        value['error_code']='raw confidential provider body'
        self.error('INVALID_RESULT',lambda:client.validate_result(value))

    def test_opaque_binding_and_separate_mail_credential_are_preserved(self):
        with patch.dict(os.environ,{'SMARTPLAN_INTEGRATION_TOKEN':TOKEN,'SMARTPLAN_INTAKE_TOKEN':'existing-mail-key'},clear=True):
            self.assertEqual(TOKEN,client.load_token())
            self.assertEqual('existing-mail-key',os.environ['SMARTPLAN_INTAKE_TOKEN'])
            self.error('USE_ONE_CREDENTIAL_SOURCE',lambda:client.load_token('unused'))
        self.error('INVALID_CREDENTIAL',lambda:client.header_credential('bad\r\ncredential'))

    @unittest.skipUnless(os.name=='posix','POSIX file mode and FIFO semantics')
    def test_private_token_file_fifo_and_symlink_are_bounded_without_hang(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{},clear=True):
            path=Path(directory)/'token';path.write_text(TOKEN,encoding='utf-8');path.chmod(0o600)
            self.assertEqual(TOKEN,client.load_token(path))
            path.chmod(0o644);self.error('UNSAFE_PRIVATE_FILE',lambda:client.load_token(path))
            link=Path(directory)/'link';link.symlink_to(path)
            self.error('UNSAFE_PRIVATE_FILE',lambda:client.load_token(link))
            fifo=Path(directory)/'fifo';os.mkfifo(fifo,0o600)
            self.error('UNSAFE_PRIVATE_FILE',lambda:client.load_token(fifo))

    def test_cli_offline_check_needs_no_key_and_never_echoes_inputs_or_argv(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{},clear=True):
            path=Path(directory)/'result.json';path.write_text(json.dumps(result()),encoding='utf-8');path.chmod(0o600)
            out=StringIO()
            with redirect_stdout(out):self.assertEqual(0,client.main(['--result',str(path),'--check']))
            self.assertEqual({'status':'checked'},json.loads(out.getvalue()))
        error=StringIO()
        with redirect_stderr(error),self.assertRaises(SystemExit):client.main(['--token',TOKEN])
        self.assertNotIn(TOKEN,error.getvalue())

    def test_source_hash_is_canonical_and_not_a_retry_timestamp(self):
        self.assertEqual(client.stable_source_id({'b':2,'a':1}),client.stable_source_id({'a':1,'b':2}))
        self.assertNotEqual(client.stable_source_id({'a':1}),client.stable_source_id({'a':2}))

    def test_whitelist_archive_manifest_and_actual_file_hashes_contain_no_private_spool(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'kit.zip';manifest=packager.build(path)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual({packager.PREFIX+name for name in packager.FILES}|{packager.PREFIX+'MANIFEST.json'},set(archive.namelist()))
                for name,digest in manifest['files_sha256'].items():
                    self.assertEqual(digest,hashlib.sha256(archive.read(packager.PREFIX+name)).hexdigest())
                self.assertNotIn(TOKEN,b''.join(archive.read(name) for name in archive.namelist()).decode('utf-8'))
            self.assertEqual(6,manifest['minimum_schema_version'])
            self.assertEqual('0.11.0-online-pilot',manifest['minimum_server_version'])
            self.assertEqual(['business_integrations'],manifest['required_server_capabilities'])
            self.assertTrue(manifest['read_only_metadata']);self.assertFalse(manifest['external_bot_connected'])
            if manifest['source_state']=='clean':self.assertRegex(manifest['source_commit'],r'^[0-9a-f]{40}$')
            else:self.assertIsNone(manifest['source_commit'])

    def test_openapi_only_exposes_two_fixed_narrow_routes_and_examples_match(self):
        spec=json.loads((DIRECTORY/'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual([{'url':'https://office.smartplan-hofmann.de'}],spec['servers'])
        self.assertEqual({'/api/v1/intake/integrations/jobs','/api/v1/intake/integrations/jobs/{id}/result'},set(spec['paths']))
        self.assertEqual({'get'},set(spec['paths']['/api/v1/intake/integrations/jobs']))
        self.assertEqual({'post'},set(spec['paths']['/api/v1/intake/integrations/jobs/{id}/result']))
        client.validate_result(result())


if __name__=='__main__':unittest.main()

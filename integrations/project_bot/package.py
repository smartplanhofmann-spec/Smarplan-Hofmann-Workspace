#!/usr/bin/env python3
"""Whitelist-only connection kit; never include a bot's credentials or results."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import zipfile

DIRECTORY=Path(__file__).resolve().parent
ROOT=DIRECTORY.parents[1]
FILES=('README.md','BOT_AUFTRAG.md','openapi.json','client.py',
       'examples/catalog_result.json','examples/error_result.json',
       'examples/google_resource_result.json','examples/onedrive_catalog_result.json',
       'examples/onedrive_resource_result.json')
PREFIX='Smartplan-Projektbot/'


def build(output):
    contents={}
    for name in FILES:
        source=DIRECTORY/name
        if source.is_symlink() or not stat.S_ISREG(source.stat().st_mode):
            raise ValueError('Only regular reviewed package sources are allowed')
        raw=source.read_bytes()
        if len(raw)>1_000_000:
            raise ValueError('Unexpected package source size')
        contents[name]=raw
    commit,state=None,'working_copy'
    try:
        revision=subprocess.check_output(['git','rev-parse','--verify','HEAD^{commit}'],cwd=ROOT,stderr=subprocess.DEVNULL,text=True).strip()
        paths=['integrations/project_bot/'+name for name in FILES]+['integrations/project_bot/package.py']
        changed=subprocess.check_output(['git','status','--porcelain','--untracked-files=all','--',*paths],cwd=ROOT,stderr=subprocess.DEVNULL)
        if not changed:commit,state=revision,'clean'
    except (OSError,subprocess.CalledProcessError):
        pass
    manifest={'format_version':1,'kind':'Smartplan project-bot connection kit','source_commit':commit,'source_state':state,
        'minimum_server_version':'0.11.0-online-pilot','minimum_schema_version':6,
        'required_server_capabilities':['business_integrations'],'providers':['google_calendar','onedrive'],
        'read_only_metadata':True,'external_bot_connected':False,
        'jobs_endpoint':'https://office.smartplan-hofmann.de/api/v1/intake/integrations/jobs',
        'files_sha256':{name:hashlib.sha256(raw).hexdigest() for name,raw in contents.items()}}
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,raw in contents.items():archive.writestr(PREFIX+name,raw)
        archive.writestr(PREFIX+'MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=build(args.output)
    print(json.dumps({'files':len(result['files_sha256']),'source_commit':result['source_commit'],'source_state':result['source_state']}))

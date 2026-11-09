"""Verify v9 with actual released Windows sources and CRLF new-kernel bytes.

This runs controlled calculations on Linux, not a Windows device. The downloaded
artifact, inner digest and every extracted Python file must match the supplied
already-authorized repository commit before any copied code is imported.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parent.parent


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--support-archive',type=Path,required=True)
    parser.add_argument('--archive-sha256',required=True)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not re.fullmatch('[a-f0-9]{64}',args.archive_sha256) or not re.fullmatch('[a-f0-9]{40}',args.source_commit):
        raise ValueError('Exact archive digest and repository commit required')
    raw=args.support_archive.read_bytes()
    if sha(raw)!=args.archive_sha256:raise ValueError('Archive digest mismatch')
    sys.path.insert(0,str(ROOT/'backend'))
    from core import canonical
    from payroll_factor_periods_2026 import calculate_factor_period_source,FACTOR_PERIOD_RULES_SHA256
    from payroll_pap_factor_2026 import FACTOR_PAP_SHA256
    fixture=json.loads((ROOT/'app/test/fixtures/payroll_factor_periods_2026_workflow.json').read_text())
    snapshot=fixture['period_case']['sources'];expected=calculate_factor_period_source(snapshot)
    verified=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        name='Smartplan_Windows_Start_und_Sicherung.zip';inner=outer.read(name)
        if sha(inner)!=outer.read(name+'.sha256').decode().split()[0]:raise ValueError('Inner archive digest mismatch')
    with tempfile.TemporaryDirectory(prefix='factor-period-windows-source-') as directory:
        target=Path(directory);prefix='Smartplan_Windows_Start_und_Sicherung/backend/'
        with zipfile.ZipFile(io.BytesIO(inner)) as archive:
            for item in archive.infolist():
                if not item.filename.startswith(prefix) or not item.filename.endswith('.py'):continue
                relative=PurePosixPath(item.filename[len(prefix):])
                if relative.is_absolute() or '..' in relative.parts or item.file_size>2_000_000:
                    raise ValueError('Unexpected source archive member')
                contents=archive.read(item)
                original=subprocess.check_output(['git','show',args.source_commit+':backend/'+str(relative)],cwd=ROOT)
                if contents.replace(b'\r\n',b'\n')!=original.replace(b'\r\n',b'\n'):
                    raise ValueError('Packaged source differs from repository commit: '+str(relative))
                path=target/str(relative);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(contents)
                verified.append(dict(name=str(relative),sha256=sha(contents),crlf=contents.count(b'\r\n')))
        kernel=(ROOT/'backend/payroll_factor_periods_2026.py').read_bytes().replace(b'\r\n',b'\n')
        (target/'payroll_factor_periods_2026.py').write_bytes(kernel.replace(b'\n',b'\r\n'))
        program=('import json,sys; from payroll_factor_periods_2026 import calculate_factor_period_source,FACTOR_PERIOD_RULES_SHA256; '
                 'from payroll_pap_factor_2026 import FACTOR_PAP_SHA256; '
                 'print(json.dumps(dict(calculation=calculate_factor_period_source(json.load(sys.stdin)),rules_sha256=FACTOR_PERIOD_RULES_SHA256,legacy_pap_sha256=FACTOR_PAP_SHA256)))')
        env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8','PYTHONPATH':str(target),'PYTHONDONTWRITEBYTECODE':'1'}
        result=subprocess.run([sys.executable,'-c',program],input=json.dumps(snapshot),text=True,
            capture_output=True,check=True,cwd=target,env=env,timeout=40)
        actual=json.loads(result.stdout)
        if actual['calculation']!=expected or actual['rules_sha256']!=FACTOR_PERIOD_RULES_SHA256:
            raise ValueError('Factor-period output or rules differ with verified Windows/CRLF sources')
    proof=dict(source_commit=args.source_commit,archive_sha256=args.archive_sha256,
        actual_windows_runtime_executed=False,source_files_verified=len(verified),sources=verified,
        new_kernel_uses_crlf=True,v9_calculation_identical=True,v9_rules_sha256=FACTOR_PERIOD_RULES_SHA256,
        result_sha256=sha(canonical(expected).encode()),legacy_v8_pap_metadata_identical=actual['legacy_pap_sha256']==FACTOR_PAP_SHA256,
        legacy_metadata_followup_required=actual['legacy_pap_sha256']!=FACTOR_PAP_SHA256)
    args.output.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({key:value for key,value in proof.items() if key!='sources'}))


if __name__=='__main__':main()

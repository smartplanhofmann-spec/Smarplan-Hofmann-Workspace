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
    parser.add_argument('--travel-fixture',type=Path,help='Also verify a controlled original travel acceptance against released sources.')
    parser.add_argument('--oneoff-fixture',type=Path,help='Also verify controlled original v6/v7 calculations and a v1 payment plan.')
    args=parser.parse_args()
    if not re.fullmatch('[a-f0-9]{64}',args.archive_sha256) or not re.fullmatch('[a-f0-9]{40}',args.source_commit):
        raise ValueError('Exact archive digest and repository commit required')
    raw=args.support_archive.read_bytes()
    if sha(raw)!=args.archive_sha256:raise ValueError('Archive digest mismatch')
    sys.path.insert(0,str(ROOT/'backend'))
    from core import canonical
    from payroll_factor_periods_2026 import calculate_factor_period_source,FACTOR_PERIOD_RULES_SHA256
    from payroll_pap_factor_2026 import FACTOR_PAP_SHA256
    from business_payroll import calculation_matches_source
    fixture=json.loads((ROOT/'app/test/fixtures/payroll_factor_periods_2026_workflow.json').read_text())
    snapshot=fixture['period_case']['sources'];expected=calculate_factor_period_source(snapshot)
    monthly=json.loads((ROOT/'app/test/fixtures/payroll_factor_2026_workflow.json').read_text())['run']['source']
    travel=json.loads(args.travel_fixture.read_text()) if args.travel_fixture else None
    oneoff=json.loads(args.oneoff_fixture.read_text()) if args.oneoff_fixture else None
    oneoff_proof=[]
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
                 'from business_payroll import _calculate_source; data=json.load(sys.stdin); source=data["factor_source"]; '
                 'legacy=_calculate_source(source); '
                 'print(json.dumps(dict(calculation=calculate_factor_period_source(data["period_snapshot"]),rules_sha256=FACTOR_PERIOD_RULES_SHA256,legacy_pap_sha256=FACTOR_PAP_SHA256,legacy_factor_calculation=legacy)))')
        env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8','PYTHONPATH':str(target),'PYTHONDONTWRITEBYTECODE':'1'}
        result=subprocess.run([sys.executable,'-c',program],input=json.dumps(dict(period_snapshot=snapshot,factor_source=monthly)),text=True,
            capture_output=True,check=True,cwd=target,env=env,timeout=40)
        actual=json.loads(result.stdout)
        if actual['calculation']!=expected or actual['rules_sha256']!=FACTOR_PERIOD_RULES_SHA256:
            raise ValueError('Factor-period output or rules differ with verified Windows/CRLF sources')
        if not calculation_matches_source(monthly,actual['legacy_factor_calculation']):
            raise ValueError('Actual released Windows v8 factor result cannot be exactly reproduced')
        if travel is not None:
            from travel_provenance_compat import calculation_matches
            code=('import json,sys;from payroll_travel_2026 import calculate;d=json.load(sys.stdin);'
                'print(json.dumps(calculate(d["trips"],d["sites"],**d["parameters"])))')
            run=subprocess.run([sys.executable,'-c',code],input=json.dumps(travel['payload']),text=True,
                capture_output=True,check=True,cwd=target,env=env,timeout=40)
            old=json.loads(run.stdout)
            if old!=travel['record']['calculation'] or not calculation_matches(travel['calculation_lf'],old,
                    trips=travel['payload']['trips'],sites=travel['payload']['sites']):
                raise ValueError('Actual released Windows travel original cannot be exactly reproduced')
        if oneoff is not None:
            from oneoff_provenance_compat import calculation_matches as oneoff_matches
            for key,case_key,module,function in (
                    ('single','one_off_case','payroll_oneoff_composition_2026','calculate_oneoff_source'),
                    ('multiple','multiple_one_off_case','payroll_multiple_oneoff_2026','calculate_multiple_source')):
                item=oneoff[key];record=item['preview']['source'][case_key];source=record['sources']['calculation_source']
                code=('import json,sys;from '+module+' import '+function+' as calculate;d=json.load(sys.stdin);'
                    'print(json.dumps(calculate(d["source"],rule_version=d["rule_version"],source_contract_version=1)))')
                run=subprocess.run([sys.executable,'-c',code],input=json.dumps(dict(source=source,rule_version=record['rule_version'])),
                    text=True,capture_output=True,check=True,cwd=target,env=env,timeout=40)
                calculated=json.loads(run.stdout)
                if calculated!=record['plan'] or not oneoff_matches(source,item['calculation_lf'],calculated):
                    raise ValueError('Actual released Windows one-off original differs: '+key)
                oneoff_proof.append(dict(kind=key,rule_version=record['rule_version'],
                    result_sha256=sha(canonical(calculated).encode()),source_sha256=sha(canonical(source).encode())))
            paid=oneoff['multiple_payment'];record=oneoff['multiple']['preview']['source']['multiple_one_off_case']
            payload=dict(source=record['sources']['calculation_source'],payments=paid['details']['payments'],
                allocations=paid['details']['settlement_allocations'],as_of='2026-11-09',
                prior_settlement=dict(run=paid['prior_payment']['sources']['run'],payment=paid['prior_payment']))
            code=('import json,sys;from payroll_multiple_payments import build_single_payment_plan;d=json.load(sys.stdin);'
                's=d.pop("source");print(json.dumps(build_single_payment_plan(s,**d)))')
            run=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),text=True,
                capture_output=True,check=True,cwd=target,env=env,timeout=40)
            if json.loads(run.stdout)!=paid['plan']:
                raise ValueError('Actual released Windows v1 original payment plan differs')
    proof=dict(source_commit=args.source_commit,archive_sha256=args.archive_sha256,
        actual_windows_runtime_executed=False,source_files_verified=len(verified),sources=verified,
        new_kernel_uses_crlf=True,v9_calculation_identical=True,v9_rules_sha256=FACTOR_PERIOD_RULES_SHA256,
        result_sha256=sha(canonical(expected).encode()),legacy_v8_pap_metadata_identical=actual['legacy_pap_sha256']==FACTOR_PAP_SHA256,
        legacy_metadata_followup_required=actual['legacy_pap_sha256']!=FACTOR_PAP_SHA256)
    proof.update(legacy_v8_compat_verified=True,
        legacy_v8_result_sha256=sha(canonical(actual['legacy_factor_calculation']).encode()),
        compatibility_rewrites_original=False,other_historical_period_metadata_followup_required=True)
    if travel is not None:
        proof.update(travel_original_matches_released_windows_result=True,
            travel_result_sha256=sha(canonical(old).encode()),travel_rule_version=old['rule_version'],
            travel_rule_hash=old['rule_hash'],travel_lf_rule_hash=travel['calculation_lf']['rule_hash'],
            travel_input_sha256=sha(canonical(travel['payload']).encode()),
            travel_fixture_sha256=sha(args.travel_fixture.read_bytes()))
    if oneoff is not None:
        proof.update(oneoff_originals_match_released_windows_results=True,oneoff_calculations=oneoff_proof,
            oneoff_v1_payment_plan_matches_released_windows_result=True,oneoff_fixture_sha256=sha(args.oneoff_fixture.read_bytes()))
    args.output.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({key:value for key,value in proof.items() if key!='sources'}))


if __name__=='__main__':main()

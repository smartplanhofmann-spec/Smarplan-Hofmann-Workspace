"""Evaluate the actual Actions gates; no Apple credentials, signing or upload."""
import json
import importlib.util
from pathlib import Path
import re
import subprocess
import unittest
import sys

ROOT=Path(__file__).resolve().parents[1]
TEST_REF='refs/heads/codex/testupdate-0.7-projects-20261104'
LEGACY_REF='refs/heads/codex/smartplan-office-0.2'
POLICY=ROOT/'scripts/ios-delivery-policy.py'
SPEC=importlib.util.spec_from_file_location('ios_delivery_policy',POLICY)
policy=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


def gates():
    workflow=(ROOT/'.github/workflows/ios-testflight.yml').read_text()
    job=workflow.split('\n  testflight:\n',1)[1]
    condition=re.search(r'^    if: (.+)$',job,re.MULTILINE).group(1)
    upload=job.split('      - name: Zu TestFlight hochladen\n',1)[1].split('      - name:',1)[0]
    match=re.search(r'^        if: (.+)$',upload,re.MULTILINE)
    return workflow,job,condition,match.group(1)if match else 'true'


def evaluate(expressions,contexts):
    # The selected, repository-owned expression subset uses JS-compatible
    # booleans, comparisons and startsWith. No shell or outside data executes.
    code="""const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
console.log(JSON.stringify(input.contexts.map(context=>input.expressions.map(expression=>
Boolean(vm.runInNewContext(expression,{...context,startsWith:(s,p)=>s.startsWith(p)},{timeout:100}))))));"""
    return json.loads(subprocess.check_output(['node','-e',code],input=json.dumps(dict(expressions=expressions,contexts=contexts)),text=True))


class ActualWorkflowGates(unittest.TestCase):
    def test_temporary_archive_never_becomes_the_published_distribution_artifact(self):
        _, job, _, _ = gates()
        order = [job.index(text) for text in (
            'name: Distributionsidentitaet aus temporaerem Apple-Export ermitteln',
            'python ../scripts/ios-archive-entitlements.py',
            'codesign --force --sign - --timestamp=none',
            'name: IPA mit erhaltener Keychain-Berechtigung final exportieren',
            'name: Signiertes iPhone-/iPad-Paket pruefen',
            "line.startswith('Authority=Apple Distribution:')",
            '--signed-entitlements "$RUNNER_TEMP/smartplan-signed-entitlements.plist"',
            'name: Smartplan-Office-iOS-',
            'name: Zu TestFlight hochladen')]
        self.assertEqual(order, sorted(order))
        artifact = job.split('name: Smartplan-Office-iOS-', 1)[1].split('      - name:', 1)[0]
        self.assertNotIn('bootstrap', artifact)
        self.assertNotIn('smartplan-archive-entitlements', artifact)
        self.assertIn('app/build/ipa/*.ipa', artifact)

    def test_prepare_signed_package_on_exact_test_branch_never_selects_upload(self):
        workflow,job,condition,upload=gates()
        context=dict(github=dict(event_name='workflow_dispatch',ref=TEST_REF),
            inputs=dict(prepare_signed_ipa=True,upload_to_testflight=False))
        self.assertEqual(evaluate([condition,upload],[context]),[[True,False]])
        self.assertIn('prepare_signed_ipa:',workflow)
        self.assertLess(job.index('name: Smartplan-Office-iOS-'),job.index('name: Zu TestFlight hochladen'))

    def test_actual_upload_always_needs_manual_event_explicit_selection_and_allowed_ref(self):
        _,_,condition,upload=gates();contexts=[];expected=[]
        for event in ('push','pull_request','workflow_dispatch'):
            for ref in (TEST_REF,LEGACY_REF,'refs/heads/main','refs/heads/codex/testupdate-0.7-foreign'):
                for prepare in (False,True):
                    for publish in (False,True):
                        contexts.append(dict(github=dict(event_name=event,ref=ref),inputs=dict(prepare_signed_ipa=prepare,upload_to_testflight=publish)))
                        accepted=event=='workflow_dispatch' and ref in (TEST_REF,LEGACY_REF) and(prepare or publish)
                        expected.append([accepted,accepted and publish])
        actual=evaluate([condition,f'({condition}) && ({upload})'],contexts)
        self.assertEqual(actual,expected)

    def test_default_inputs_and_execution_order_preserve_unsigned_only_start(self):
        workflow,job,condition,upload=gates()
        for name in ('prepare_signed_ipa','upload_to_testflight'):
            block=re.search(r'^      '+re.escape(name)+r':\n((?:^        .*\n)+)',workflow,re.MULTILINE).group(1)
            self.assertIn('default: false',block)
            self.assertIn('type: boolean',block)
        context=dict(github=dict(event_name='workflow_dispatch',ref=TEST_REF),inputs={})
        self.assertEqual(evaluate([condition,upload],[context]),[[False,False]])
        self.assertIn('needs: unsigned',job)
        self.assertLess(job.index('uses: actions/checkout@v4'),job.index('python ../scripts/ios-delivery-policy.py'))
        self.assertLess(job.index('python ../scripts/ios-delivery-policy.py'),job.index('name: Apple-Secrets pruefen'))
        self.assertLess(job.index('codesign --verify --deep --strict'),job.index('name: Smartplan-Office-iOS-'))
        self.assertIn('if: always()',job.split('name: API-Schluessel loeschen',1)[1])


class DeliveryPolicy(unittest.TestCase):
    def test_guard_agrees_with_actual_job_for_all_48_selections(self):
        _,_,condition,upload=gates();contexts=[];actual=[]
        for event in ('push','pull_request','workflow_dispatch'):
            for ref in (TEST_REF,LEGACY_REF,'refs/heads/main','refs/heads/codex/testupdate-0.7-foreign'):
                for prepare in (False,True):
                    for publish in (False,True):
                        contexts.append(dict(github=dict(event_name=event,ref=ref),inputs=dict(prepare_signed_ipa=prepare,upload_to_testflight=publish)))
                        try:
                            result=policy.authorize(event=event,ref=ref,commit='a'*40,
                                prepare_signed=str(prepare).lower(),upload=str(publish).lower())
                        except ValueError:
                            actual.append([False,False])
                        else:
                            self.assertEqual(result['source_commit'],'a'*40)
                            self.assertEqual(result['mode'],'upload' if publish else 'signed_only')
                            actual.append([True,result['upload_to_testflight']])
        self.assertEqual(actual,evaluate([condition,f'({condition}) && ({upload})'],contexts))

    def test_guard_rejects_ambiguous_flags_and_noncanonical_source_before_any_action(self):
        original=dict(event='workflow_dispatch',ref=TEST_REF,commit='a'*40,prepare_signed='true',upload='false')
        invalid=[dict(commit=value)for value in ('HEAD','a'*39,'A'*40,'a'*40+'\n',None)]
        invalid +=[dict(prepare_signed=value)for value in ('','TRUE','1',True,None)]
        invalid +=[dict(upload=value)for value in ('','False','0',False,None)]
        invalid +=[dict(ref=TEST_REF+'/other'),dict(ref=TEST_REF+'\n'),dict(event='workflow_dispatch\n')]
        for replacement in invalid:
            with self.subTest(replacement=replacement),self.assertRaises(ValueError):
                policy.authorize(**(original|replacement))

    def test_actual_cli_prepares_without_upload_and_rejects_missing_selection(self):
        args=[sys.executable,str(POLICY),'--event','workflow_dispatch','--ref',TEST_REF,'--commit','b'*40]
        prepared=subprocess.run(args+['--prepare-signed','true','--upload','false'],capture_output=True,text=True)
        self.assertEqual(prepared.returncode,0,prepared.stderr)
        decision=json.loads(prepared.stdout)
        self.assertEqual(decision,dict(schema_version=1,mode='signed_only',ref=TEST_REF,source_commit='b'*40,upload_to_testflight=False))
        uploaded=subprocess.run(args+['--prepare-signed','false','--upload','true'],capture_output=True,text=True)
        self.assertEqual(uploaded.returncode,0,uploaded.stderr)
        self.assertEqual(json.loads(uploaded.stdout)['mode'],'upload')
        for suffix in ([],['--prepare-signed','false','--upload','false'],['--prepare-signed','true','--upload','TRUE']):
            denied=subprocess.run(args+suffix,capture_output=True,text=True)
            self.assertEqual(denied.returncode,2)
            self.assertEqual(denied.stdout,'')


if __name__=='__main__':unittest.main()

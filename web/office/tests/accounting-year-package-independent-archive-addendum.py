"""Independent follow-up of new archives and their external trust boundary.

Uses the trusted repository verifier, not code extracted from the ZIP.
No extraction, product mutation, database access or network.
"""
from pathlib import Path
import base64
import hashlib
import importlib.util
import io
import json
import zipfile

ROOT=Path(__file__).resolve().parents[3]
fixture_path=ROOT/'docs/fixtures/accounting_year_package_v1.json'
fixture_raw=fixture_path.read_bytes()
expected_fixture='a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0'
assert hashlib.sha256(fixture_raw).hexdigest()==expected_fixture
assert fixture_raw==(ROOT/'app/test/fixtures/accounting_year_package_v1.json').read_bytes()
fixtures=json.loads(fixture_raw)
verifier_path=ROOT/'backend/accounting_year_verify_v1.py'
spec=importlib.util.spec_from_file_location('independent_year_verifier',verifier_path)
verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
results=[]
for name,scenario in fixtures['scenarios'].items():
    metadata,export=scenario['metadata'],scenario['export']
    raw=base64.b64decode(scenario['archive_base64'],validate=True)
    # The anchor comes from separately authenticated metadata, never from ZIP content.
    anchor=metadata['sha256']
    assert len(raw)==metadata['size'] and hashlib.sha256(raw).hexdigest()==anchor
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=archive.namelist()
        assert len(set(names))==len(names) and names==sorted(names)
        assert all(i.compress_type==zipfile.ZIP_STORED and i.date_time==(1980,1,1,0,0,0) for i in archive.infolist())
        manifest=json.loads(archive.read('manifest.json'))
        assert manifest['intrinsic_dependency_closure'] is False
        assert manifest['required_trust']=='separately_authenticated_archive_sha256'
        assert set(names)=={'manifest.json'}|{v['path'] for v in manifest['files']}
        for member in manifest['files']:
            content=archive.read(member['path'])
            assert len(content)==member['size'] and hashlib.sha256(content).hexdigest()==member['sha256']
        originals=[v for v in names if v.startswith('originals/')]
        assert len(originals)==metadata['original_count']
        for member in originals:
            assert member=='originals/'+hashlib.sha256(archive.read(member)).hexdigest()+'.bin'
        assert archive.read('verify_year_package.py')==verifier_path.read_bytes()
        assert json.loads(archive.read('report.json'))==export['report']
        assert archive.read('postings.csv')==export['csv'].encode('utf-8')
        for field in ['instance_id','year','export_id','export_hash','private_source_boundaries','original_year_complete','official_tax_return','datev_certified','private_personnel_originals_included']:
            assert manifest[field]==metadata[field]
        assert metadata['original_year_complete']==export['report']['complete_for_recorded_sources']
        assert metadata['official_tax_return'] is False and metadata['datev_certified'] is False and metadata['private_personnel_originals_included'] is False
    validated=verifier.verify(raw,anchor)
    assert validated['verified'] is True and validated['intrinsic_dependency_closure'] is False
    assert validated['verification_basis']=='separately_authenticated_archive_sha256_and_structural_checks'
    assert validated['sha256']==anchor and validated['original_year_complete']==metadata['original_year_complete']
    rejected=[]
    corrupt=bytearray(raw);corrupt[-1]^=1
    for label,content,trusted in [('missing_external_anchor',raw,None),('wrong_external_anchor',raw,'0'*64),('changed_archive_original_anchor',bytes(corrupt),anchor)]:
        try:verifier.verify(content,trusted)
        except ValueError:rejected.append(label)
        else:raise AssertionError(name+': '+label+' unexpectedly accepted')
    results.append(dict(scenario=name,archive_sha256=anchor,size=len(raw),files_including_manifest=len(names),originals=len(originals),original_year_complete=metadata['original_year_complete'],private_source_boundaries=metadata['private_source_boundaries'],intrinsic_dependency_closure=False,external_anchor_source='authenticated_metadata.sha256',negative_cases_rejected=rejected))
assert fixtures['scenarios']['old_after_profile_change']['archive_base64']==fixtures['scenarios']['ordinary_correction']['archive_base64']
print(json.dumps(dict(fixture_sha256=expected_fixture,fixture_size=len(fixture_raw),verified_archives=len(results),rejected_negative_cases=sum(len(v['negative_cases_rejected']) for v in results),scenarios=results,trusted_repository_verifier_sha256=hashlib.sha256(verifier_path.read_bytes()).hexdigest(),no_extraction=True,no_archive_script_execution=True,no_database=True,no_network=True,intrinsic_dependency_closure=False),indent=2))

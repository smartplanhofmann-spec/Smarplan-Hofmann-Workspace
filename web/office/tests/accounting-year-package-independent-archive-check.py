"""Independent ZIP/member/original comparison, without extraction or script execution."""
from pathlib import Path
import base64
import hashlib
import io
import json
import zipfile

ROOT=Path(__file__).resolve().parents[3]
fixtures=json.loads((ROOT/'docs/fixtures/accounting_year_package_v1.json').read_text())
results=[]
for name,scenario in fixtures['scenarios'].items():
    metadata,export=scenario['metadata'],scenario['export']
    raw=base64.b64decode(scenario['archive_base64'],validate=True)
    assert len(raw)==metadata['size'] and hashlib.sha256(raw).hexdigest()==metadata['sha256']
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=archive.namelist()
        assert len(set(names))==len(names) and names==sorted(names)
        assert all(i.compress_type==zipfile.ZIP_STORED and i.date_time==(1980,1,1,0,0,0) for i in archive.infolist())
        manifest=json.loads(archive.read('manifest.json'))
        assert set(names)=={'manifest.json'}|{v['path'] for v in manifest['files']}
        for member in manifest['files']:
            content=archive.read(member['path'])
            assert len(content)==member['size'] and hashlib.sha256(content).hexdigest()==member['sha256']
        originals=[v for v in names if v.startswith('originals/')]
        assert len(originals)==metadata['original_count']
        for member in originals:
            content=archive.read(member)
            assert member=='originals/'+hashlib.sha256(content).hexdigest()+'.bin'
        assert json.loads(archive.read('report.json'))==export['report']
        assert archive.read('postings.csv')==export['csv'].encode('utf-8')
        for field in ['instance_id','year','export_id','export_hash','private_source_boundaries','original_year_complete','official_tax_return','datev_certified','private_personnel_originals_included']:
            assert manifest[field]==metadata[field]
        assert metadata['original_year_complete']==export['report']['complete_for_recorded_sources']
        assert metadata['official_tax_return'] is False and metadata['datev_certified'] is False and metadata['private_personnel_originals_included'] is False
        results.append(dict(scenario=name,archive_sha256=metadata['sha256'],files=len(names),originals=len(originals),original_year_complete=metadata['original_year_complete'],private_source_boundaries=metadata['private_source_boundaries']))
print(json.dumps(dict(verified=True,scenarios=results,no_extraction=True,no_archive_script_execution=True),indent=2))

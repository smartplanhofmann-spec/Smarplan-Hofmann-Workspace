"""Actual disposable year-opening workflow DTOs; separate from frozen API fixture."""
import argparse,json,sys,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'backend'))
from test_accounting_year_openings import YearOpeningWorkflow
from business_accounting_year_openings import public_source,TABLES
from business_accounting_open_items import TABLES as ITEM_TABLES
from business_accounting import Accounting
parser=argparse.ArgumentParser();parser.add_argument("--output",default="accounting-year-values-ui.json");args=parser.parse_args()
f=YearOpeningWorkflow('runTest');f.setUp()
try:
 initial=f.api.state(f.owner);body=f.body();preview=f.api.preview(f.owner,body)
 before=dict(state=initial,open_items=f.f.api.state(f.owner),euer=f.f.euer.api.state(f.owner))
 entry,command=f.save();source=public_source(f.office,'2026');sources=f.f.euer.api.sources(f.owner)
 before.update(report=f.f.euer.api.report(f.owner,2026),journal=f.f.euer.api.journal(f.owner,25,0),accounts=Accounting(f.office).accounts(f.owner))
 euer_body=f.f.euer.body('opening_year_values',dict(year='2026',revision=source['revision'],source_hash=source['source_hash']))
 euer_preview=f.f.euer.api.preview(f.owner,euer_body)
 posted=f.classify(entry)
 result=dict(schema_version=1,synthetic=True,before=before,preview=preview,command=command,entry=entry,source=source,sources=sources,originals=[dict(metadata=o,content_base64=base64.b64encode(bytes(f.office.db.execute('SELECT original FROM '+TABLES[0]+' WHERE id=?',(o['id'],)).fetchone()[0])).decode()) for o in initial['originals']],state=f.api.state(f.owner),history=f.api.history(f.owner,'2026'),euer_body=euer_body,euer_preview=euer_preview,euer_entry=posted)
 result['opening_items_originals']=[dict(metadata=o,content_base64=base64.b64encode(bytes(f.office.db.execute('SELECT original FROM '+ITEM_TABLES[0]+' WHERE id=?',(o['id'],)).fetchone()[0])).decode()) for o in before['open_items']['originals']]
 f.f.euer.configure(vat_timing=None,bookkeeping_start=None)
 result['dateless_state']=f.api.state(f.owner)
 f.f.euer.configure(vat_timing=None,bookkeeping_start='2026-11-01')
 result['unconfigured_state']=f.api.state(f.owner)
 out=Path(__file__).with_name('fixtures')/args.output;out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(out)
finally:f.doCleanups()

"""Read-only reproducible merge audit. Never executes product code."""
import ast, collections, hashlib, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE='13af5bc1147170948c5de8fa9f831a7215974cb5'
def original(path): return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT,text=True)
def read(path):
    target=ROOT/path
    if not target.exists() and path.startswith('work/verification/open-items-merge/'):
        target=Path(__file__).resolve().parent/Path(path).name
    return target.read_text()
def sha(path): return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
def constants(text,names):
    env={}
    for n in ast.parse(text).body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in names:
            env[n.targets[0].id]=eval(compile(ast.Expression(n.value),'<literal>','eval'),{'__builtins__':{},'tuple':tuple},env)
        elif isinstance(n,ast.AugAssign) and isinstance(n.target,ast.Name) and n.target.id in env and isinstance(n.op,ast.Add): env[n.target.id]+=ast.literal_eval(n.value)
    return env
prepared=json.loads(read('work/verification/open-items-merge/prepared.json'))
resolved=json.loads(read('work/verification/open-items-merge/resolved.json'))
assert prepared['target_commit']==resolved['target_commit']==BASE
assert len(prepared['files'])==len(resolved['files'])==193
manifests=[]
for item in prepared['owner_manifests']:
    assert sha(item['path'])==item['sha256']
    manifests.append(item)
files=[]
for item in resolved['files']:
    actual=sha(item['path']);assert actual==item['resolved_sha256'],item['path']
    files.append(dict(path=item['path'],sha256=actual,owner_sha256=item['sha256'],kind=item['kind'],owner_exact=actual==item['sha256']))
packages={}
for path in ['scripts/native-release.py','scripts/package-windows-support.py']:
    before=constants(original(path),['BACKEND_FILES','OPERATOR_FILES']);after=constants(read(path),['BACKEND_FILES','OPERATOR_FILES'])
    packages[path]={}
    for name,items in before.items():
        current=after[name]
        assert len(current)==len(set(current))
        assert set(items)<=set(current)
        assert all((ROOT/('backend' if name=='BACKEND_FILES' else '')/v).is_file() for v in current)
        packages[path][name]=dict(before=len(items),after=len(current),added=sorted(set(current)-set(items)),removed=[])
assert constants(read('scripts/native-release.py'),['BACKEND_FILES','OPERATOR_FILES'])==constants(read('scripts/package-windows-support.py'),['BACKEND_FILES','OPERATOR_FILES'])
for label,name in [('smartplanFile','BACKEND_FILES'),('smartplanOperatorFile','OPERATOR_FILES')]:
    candidates=[tuple(re.findall("'([^']+)'",m)) for m in re.findall(r'foreach \(\$'+label+r' in @\((.*?)\)\)',read('.github/workflows/checks.yml'),re.S)]
    assert constants(read('scripts/native-release.py'),['BACKEND_FILES','OPERATOR_FILES'])[name] in candidates
registries={}
for path,name in [('backend/business_api.py','MODULES'),('backend/business_schema.py','MODULE_NAMES')]:
    a=constants(original(path),[name])[name];b=constants(read(path),[name])[name]
    assert tuple(v for v in b if v!='business_accounting_open_items')==a
    registries[path]=dict(before=len(a),after=len(b),added=['business_accounting_open_items'],preserved_order=True)
def functions(text):return {n.name:n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
a=functions(original('backend/business_schema.py'));b=functions(read('backend/business_schema.py'))
assert set(a)<=set(b)
changed=[name for name in a if ast.dump(a[name])!=ast.dump(b[name])]
assert changed==['financial_accounting_horizon','_validate_financial_accounting_horizon','_reconcile_financial_report']
n=b['_validate_financial_accounting_horizon'];n.body=[v for v in n.body if not (isinstance(v,ast.If) and ast.unparse(v.test)=='report_schema == 15')]
assert ast.dump(n)==ast.dump(a['_validate_financial_accounting_horizon'])
# Entire previous native session is retained as an ordered line subsequence.
old=original('app/lib/business_session.dart').splitlines();new=read('app/lib/business_session.dart').splitlines();cursor=iter(new)
assert all(any(candidate==line for candidate in cursor) for line in old)
session=dict(old_lines=len(old),new_lines=len(new),added=len(new)-len(old),deleted=0)
old_office=original('web/office/office.js');new_office=read('web/office/office.js')
start=old_office.index('export class OfficeApi');end=old_office.index('export async function assistantPendingAuthorize',start)
old_class=old_office[start:end];new_class=new_office[new_office.index('export class OfficeApi'):new_office.index('export async function assistantPendingAuthorize')]
new_class=new_class.replace("      if(old&&path.startsWith('/business/accounting/open-items'))await oiPendingAuthorize(this,{key,path});\n",'')
new_class=new_class.replace("const protectedAccounting=path.startsWith('/business/accounting/open-items')||",'const protectedAccounting=')
assert new_class==old_class
old_visibility=next(line for line in old_office.splitlines() if "document.addEventListener('visibilitychange'" in line)
new_visibility=next(line for line in new_office.splitlines() if "document.addEventListener('visibilitychange'" in line)
assert new_visibility.replace('openItemWorkspace.clear();','').replace(', [data-open-items]','')==old_visibility
# Both HTTP implementations retain every previous size/allowlist decision.
transport={}
for path,prefix in [('backend/server.py','/api'),('backend/online/web.py','')]:
    text=read(path).replace(", '"+prefix+"/business/accounting/open-items/originals'",'')
    if path.endswith('web.py'):
        text=text.replace("'accounting-open-items.js': 'text/javascript', 'accounting-open-items-contract.js': 'text/javascript', ",'')
    assert text==original(path),path
    transport[path]=dict(previous_exact_except_new_original_route_and_web_modules=True)
tracked=subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
known={v['path'] for v in files}
extras=sorted(path for path in set(tracked+untracked)-known if path.startswith(('backend/','app/','web/','scripts/','.github/')))
expected_extras=['backend/online/test_catalog_v2_source5_assets_restore_pg.py','backend/online/test_events_catalog_assets_source5_restore_pg.py','backend/online/test_open_items_events_catalog_restore_pg.py']
assert extras==expected_extras,extras
protected=[]
paths=['app/lib/api.dart','app/lib/business_widgets.dart','backend/business_catalog_prices.py','backend/business_catalog_imports.py','backend/business_documents.py','backend/business_pricing.py','backend/business_sales.py','backend/business_purchasing.py','backend/business_inventory.py','backend/business_company_events.py','backend/company_event_sources.py','backend/company_event_worker.py','backend/business_payroll_multiple_cases.py','backend/payroll_multiple_oneoff_2026.py','backend/payroll_multiple_runs.py','backend/payroll_multiple_payments.py','app/lib/business_company_event_contract.dart','app/lib/business_company_events.dart','app/lib/business_catalog_prices.dart','web/office/company-events-contract.js','web/office/company-events.js','web/office/catalog-prices.js','web/office/payroll-multiple-cases.js']
for path in paths:
    assert (ROOT/path).read_bytes()==subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT),path
    protected.append(dict(path=path,sha256=sha(path)))
result=dict(base_commit=BASE,owner_base_commit=prepared['base_commit'],owner_manifests=manifests,files=files,summary=dict(total=193,owner_exact=sum(v['owner_exact'] for v in files),resolved_exact=len(files),kinds=dict(collections.Counter(v['kind'] for v in files)),conflicts=[v['path'] for v in files if v['kind']=='conflict']),packages=packages,ci_lists_identical=True,registries=registries,schema=dict(function_count=len(a),unchanged_function_count=len(a)-len(changed),changed_functions=changed,previous_report_validator_ast_unchanged=True),native_session=session,office_api=dict(previous_class_exact_except_two_additive_open_item_hooks=True,previous_visibility_handler_exact_except_open_items=True),protected_runtime_files_byte_equal_to_base=protected,http_transport=transport,root_additional_tests=[dict(path=v,sha256=sha(v)) for v in extras],unexpected_additional_runtime_files=[],runtime_edits_by_reviewer=[])
print(json.dumps(result,indent=2))

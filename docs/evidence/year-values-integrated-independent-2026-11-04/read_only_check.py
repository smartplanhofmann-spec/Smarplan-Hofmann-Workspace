from pathlib import Path
import ast, hashlib, json, subprocess, tempfile, shutil, datetime
root=Path.cwd(); base='2e2ed5ca33b928216b940c6334cdfbbca0a14c27'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def old(p): return subprocess.check_output(['git','show',base+':'+p])
def matches(rows,hash_key='sha256'):
 return [{'path':p,'expected':v[hash_key] if isinstance(v,dict) else v,'actual':sha(Path(p))} for p,v in rows.items() if sha(Path(p))!=(v[hash_key] if isinstance(v,dict) else v)]
def refs(rows):
 for p,v in rows.items(): assert sha(Path(p))==v['sha256'],p
 return rows
proof={}; bm=read('work/verification/year-values-backend-merge/resolved.json'); vp=read('work/verification/year-package-v2-merge/resolved.json'); scopes=read('docs/evidence/year-values-current-scope-adaptations-2026-11-04.json')
proof['backend_owner_manifest']=refs({bm['owner_manifest']['path']:{'sha256':bm['owner_manifest']['sha256']}})
proof['recovered_backend_baselines']={}
for folder,field in [('base','before_sha256'),('current','current_sha256'),('incoming','sha256'),('candidate','candidate_sha256')]:
 records={}
 for f in bm['files']:
  if f.get(field) is None: continue
  p=Path('work/verification/year-values-backend-merge')/folder/f['path'];assert p.exists(),str(p);assert sha(p)==f[field],str(p);records[f['path']]=f[field]
 proof['recovered_backend_baselines'][folder]=records
assert len(bm['files'])==60
proof['v2_direct']={f['path']:f['sha256'] for f in vp['direct_files']}; assert not matches(proof['v2_direct'])
proof['v2_narrow']={f['path']:f['sha256'] for f in vp['narrow_after']};assert not matches(proof['v2_narrow'])
proof['scope_test_adaptations']={f['path']:f['after_sha256'] for f in scopes['files']};assert not matches(proof['scope_test_adaptations'])
# Final backend product path equality after its documented archive overlay.
backend_final={f['path']:f['resolved_sha256'] for f in bm['files'] if f['path'].startswith('backend/') and '/test' not in f['path']}
backend_final.update({p:h for p,h in vp['after_file_sha256'].items() if p.startswith('backend/') and '/test' not in p});assert not matches(backend_final);proof['backend_final']=backend_final
browser=read('docs/evidence/year-values-browser-integrated-2026-11-04/manifest.json'); follow=read('docs/evidence/year-values-browser-profile-void-integrated-2026-11-04/manifest.json'); native=read('docs/evidence/year-values-native-integrated-2026-11-04/manifest.json')
proof['handoff_refs']={}
for r in [browser['source_owner_manifest'],browser['source_review_manifest']]:proof['handoff_refs'][r['path']]={'sha256':r['sha256']}
proof['handoff_refs'].update(native['source_handoffs'])
for name in ['owner_manifest','independent_manifest']:proof['handoff_refs'][follow[name]]={'sha256':follow[name+'_sha256']}
refs(proof['handoff_refs'])
initial={r['path']:r['after_sha256'] for r in browser['files']};addition={r['path']:r['after_sha256'] for r in follow['files']};final_browser=initial|addition
assert not matches(final_browser);proof['browser_final']=final_browser;proof['browser_initial_paths']=len(initial);proof['browser_followup_paths']=len(addition)
assert not matches(native['files']);proof['native_final']=native['files'];proof['native_owner_checks']=native['checks']
proof['native_shared_reverse_patch']={};before=read('docs/evidence/year-values-native-integrated-2026-11-04/before-hashes.json');patch=root/'docs/evidence/year-values-native-integrated-2026-11-04/integration.patch'
with tempfile.TemporaryDirectory(prefix='year-values-independent-readonly-') as tmp:
 for p in ['app/lib/business_session.dart','app/lib/business_accounting_euer.dart']:
  target=Path(tmp)/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
 r=subprocess.run(['patch','-R','--fuzz=0','-p1','-i',str(patch)],cwd=tmp,capture_output=True,text=True);assert r.returncode==0,r.stdout+r.stderr
 for p in ['app/lib/business_session.dart','app/lib/business_accounting_euer.dart']:
  assert sha(Path(tmp)/p)==before[p]['sha256'];proof['native_shared_reverse_patch'][p]=before[p]['sha256']
# Original schema validator arms are exact AST matches; only 16 is additive.
a=next(n for n in ast.parse(old('backend/business_schema.py')).body if isinstance(n,ast.FunctionDef) and n.name=='_validate_financial_accounting_horizon');b=next(n for n in ast.parse(Path('backend/business_schema.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name==a.name)
def arms(fn):return {ast.unparse(n.test):ast.dump(n,include_attributes=False) for n in fn.body if isinstance(n,ast.If)}
x,y=arms(a),arms(b);assert all(y.get(k)==v for k,v in x.items());assert set(y)-set(x)=={'report_schema == 16'};proof['old_horizon_branches_preserved']=list(x)
def constant(src,name):
 n=next(n for n in ast.parse(src).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets));return eval(compile(ast.Expression(n.value),'<constant>','eval'),{'__builtins__':{},'tuple':tuple})
proof['registrations']={}
for p,name in [('backend/business_api.py','MODULES'),('backend/business_schema.py','MODULE_NAMES'),('backend/company_export_catalog.py','COLUMNS')]:
 a=constant(old(p),name);b=constant(Path(p).read_text(),name);assert set(a)<=set(b);assert not isinstance(a,dict) or all(a[k]==b[k] for k in a);proof['registrations'][p]={'old_count':len(a),'current_count':len(b),'added':sorted(set(b)-set(a)),'old_entries_preserved':True}
proof['package_lists']={}
for p in ['scripts/native-release.py','scripts/package-windows-support.py']:
 proof['package_lists'][p]={'sha256':sha(Path(p))}
 for name in ['BACKEND_FILES','OPERATOR_FILES']:
  a=constant(old(p),name);b=constant(Path(p).read_text(),name);assert set(a)<=set(b);assert len(b)==len(set(b));proof['package_lists'][p][name]={'old_count':len(a),'current_count':len(b),'added':sorted(set(b)-set(a)),'old_entries_preserved':True}
tracked=subprocess.check_output(['git','ls-tree','-r','--name-only',base,'backend'],text=True).splitlines();protected=[p for p in tracked if Path(p).name.startswith(('business_payroll','payroll_','business_company_events','company_event_','business_catalog','accounting_year_package_v1','accounting_year_verify_v1')) or Path(p).name in ('business_pricing.py','business_documents.py','business_sales.py','business_inventory.py','business_purchasing.py','business_bank_reconciliation.py','accounting_open_item_sources.py')]
for p in protected:assert Path(p).read_bytes()==old(p),p
proof['protected_backend_unchanged']={p:sha(Path(p)) for p in protected}
oldoffice=old('web/office/office.js').decode();newoffice=Path('web/office/office.js').read_text();lines=[line for line in oldoffice.splitlines() if "document.addEventListener('visibilitychange'" in line];assert all(line in newoffice.splitlines() for line in lines);proof['original_visibility_handlers_exact']=lines
oldeuer=old('web/office/accounting-euer.js').decode();a=oldeuer.index(' async function exported(');b=oldeuer.index('\n async function ',a+1);original_exported=oldeuer[a:b];assert original_exported in Path('web/office/accounting-euer.js').read_text();proof['legacy_exported_function_sha256']=hashlib.sha256(original_exported.encode()).hexdigest()
ui_protected=['app/lib/api.dart','web/office/company-events-contract.js','web/office/company-events.js','app/lib/business_company_event_contract.dart','app/lib/business_company_events.dart','web/office/catalog-prices.js']
for p in ui_protected:assert Path(p).read_bytes()==old(p),p
proof['protected_ui_unchanged']={p:sha(Path(p)) for p in ui_protected};proof['own_tests_executed_for_merge']=False;proof['pg_used']=False
registration=read('docs/evidence/year-values-client-registrations-2026-11-04.json');assert all(sha(Path(p))==v['after_sha256'] for p,v in registration['files'].items())
ci=Path('.github/workflows/checks.yml').read_text();assert all(p in ci and Path(p).exists() for p in registration['operator_added']);assert registration['browser_runner'] in ci
import re
pattern=r'(?:backend/|online\.|tests/|app/test/)[A-Za-z0-9_./-]+'
oldpaths=set(re.findall(pattern,old('.github/workflows/checks.yml').decode()));newpaths=set(re.findall(pattern,ci));assert not oldpaths-newpaths
proof['client_registrations']=registration;proof['old_ci_path_tokens_preserved']=len(oldpaths)
proposal_path='work/verification/year-values-historical-pg-scope-review-2026-11-04/proposal.json';proposal=read(proposal_path)
assert sha(Path(proposal['patch']['path']))==proposal['patch']['sha256'];assert all(sha(Path(v['path']))==v['before_sha256'] for v in proposal['proposed_changes'])
proof['pending_pg_test_only_proposal']={'path':proposal_path,'sha256':sha(Path(proposal_path)),'patch':proposal['patch'],'status_at_review':'not yet applied; no PostgreSQL run by this reviewer','changes':proposal['proposed_changes']}
proof['recorded_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();proof['base_commit']=base
Path('/tmp/year-values-independent-merge-check.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'backend_baseline_counts':{k:len(v) for k,v in proof['recovered_backend_baselines'].items()},'v2_direct':len(proof['v2_direct']),'browser_final_unique':len(final_browser),'native_bound_paths':len(native['files']),'protected_backend':len(protected),'all_assertions':True,'package_counts':{p:{n:v[n]['current_count'] for n in ['BACKEND_FILES','OPERATOR_FILES']} for p,v in proof['package_lists'].items()}},indent=2))

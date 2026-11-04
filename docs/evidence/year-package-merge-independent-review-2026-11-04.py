"""Read-only manifest/registration checks; produces only independent evidence."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
def digest(raw): return hashlib.sha256(raw).hexdigest()
def original(path): return subprocess.check_output(['git', 'show', 'HEAD:'+path], cwd=ROOT, text=True)
def assigned(text, name):
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise AssertionError(name)

prepared = json.loads((ROOT/'work/verification/year-package-merge/prepared.json').read_text())
resolved = json.loads((ROOT/'work/verification/year-package-merge/resolved.json').read_text())
assert len(prepared['files']) == len(resolved['files']) == 191
assert prepared['target_commit'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
checked = []
for row in resolved['files']:
    expected = row.get('resolved_sha256', row['candidate_sha256'])
    observed = digest((ROOT/row['path']).read_bytes())
    assert observed == expected, (row['path'], observed, expected)
    checked.append({'path': row['path'], 'sha256': observed})

packages = {}
for path in ('scripts/native-release.py', 'scripts/package-windows-support.py'):
    before, after = original(path), (ROOT/path).read_text()
    packages[path] = {}
    for name, count in (('BACKEND_FILES',139), ('OPERATOR_FILES',178)):
        a,b = assigned(before,name), assigned(after,name)
        assert len(b)==len(set(b))==count and set(a)<=set(b)
        declared=resolved['package_arrays'][path][name]
        assert a==declared['before'] and b==declared['after']
        packages[path][name]={'before_count':len(a),'after_count':len(b),'removed':[], 'added':sorted(set(b)-set(a))}

ci=(ROOT/'.github/workflows/checks.yml').read_text(); old_ci=original('.github/workflows/checks.yml')
for marker,name,count in [('foreach ($smartplanFile in @(','BACKEND_FILES',139),('foreach ($smartplanOperatorFile in @(','OPERATOR_FILES',178)]:
    extra='business_accounting.py' if name=='BACKEND_FILES' else 'CRM_ERP_EUER_BETRIEB.md'
    a=next(l for l in old_ci.splitlines() if marker in l and extra in l)
    b=next(l for l in ci.splitlines() if marker in l and extra in l)
    old_values=re.findall("'([^']+)'",a); values=re.findall("'([^']+)'",b)
    assert len(values)==len(set(values))==count and set(old_values)<=set(values)
    assert set(values)==set(assigned((ROOT/'scripts/native-release.py').read_text(),name))
assert "python -m unittest discover -s backend/online -p test_accounting_year_package_pg.py -v" in ci
assert 'node tests/accounting-year-package-e2e.cjs' in ci

web=(ROOT/'backend/online/web.py').read_text(); old_web=original('backend/online/web.py')
def static_names(text):
    found=set()
    for n in ast.walk(ast.parse(text)):
        if not isinstance(n,(ast.Set,ast.Dict,ast.List,ast.Tuple)):continue
        try:value=ast.literal_eval(n)
        except (ValueError,TypeError):continue
        if 'accounting-euer.js' in value:found.update(value)
    return found
old_static,new_static=static_names(old_web),static_names(web)
assert old_static and old_static<=new_static
assert new_static-old_static=={'accounting-year-package.js','accounting-year-package-contract.js'}

# The native merge must consist exactly of the reviewed import and navigation,
# leaving all existing invoice, lifecycle, export and open-item code intact.
app_path='app/lib/business_accounting_euer.dart';old_app=original(app_path);app=(ROOT/app_path).read_text()
assert app.replace("import 'business_accounting_year_evidence.dart';\n",'').replace('''                  if (yearEvidenceReadable(widget.session))
                    OutlinedButton(
                      onPressed: () => Navigator.of(context).push<void>(
                        MaterialPageRoute(
                          builder: (_) => BusinessYearEvidencePage(
                            session: widget.session,
                            exportEntry: yearEvidenceCopy(entry),
                          ),
                        ),
                      ),
                      child: const Text(
                        'Original-/Journal-Jahresnachweis öffnen',
                      ),
                    ),
''','')==old_app

office=(ROOT/'web/office/office.js').read_text();old_office=original('web/office/office.js')
for name in ('endSession','openItemWorkspace','companyEvents'):
    if name=='endSession':
        assert next(l for l in office.splitlines() if l.startswith('function endSession()'))==next(l for l in old_office.splitlines() if l.startswith('function endSession()'))
for marker in ('keepOpenItems','keepCompanyEvents','openItemWorkspace.clear();','companyEvents.clear();','accountingEuer.invalidateExport();','[data-year-package]','[data-year-export]'):
    assert marker in office
euer=(ROOT/'web/office/accounting-euer.js').read_text();old_euer=original('web/office/accounting-euer.js')
for prefix in (' function privateStamp()', ' function privateCurrent(', ' async function reviewOriginal('):
    assert next(l for l in euer.splitlines() if l.startswith(prefix))==next(l for l in old_euer.splitlines() if l.startswith(prefix))
for marker in ('intent!==exportGeneration','ui.privateContext()!==visibleContext','content&&!content.isConnected','await readAgain();ui.jsonDownload','await readAgain();ui.textDownload','await ui.openYearPackage(value)'):
    assert marker in euer

result={'date':'2026-11-04','reviewer':'finish_v6_backend','scope':'Independent read-only V1 merge review, no regression execution',
    'target_commit':prepared['target_commit'],'checked_handoff_files':checked,
    'prepared_sha256':digest((ROOT/'work/verification/year-package-merge/prepared.json').read_bytes()),
    'resolved_sha256':digest((ROOT/'work/verification/year-package-merge/resolved.json').read_bytes()),
    'packages':packages,'ci_counts':{'backend':139,'operator':178},'static_added':sorted(new_static-old_static),
    'app_original_code_exactly_preserved':True,'manual_conflict_review':['Native EÜR fifteen additive lines only','Browser EÜR original/open-item context guards preserved; export intent, fresh authorization, original readback and dialog guard combined','Office original CompanyEvents/OpenItems lifecycle, background and modal guards preserved with both yearly export views'],
    'confirmed_findings':[],'product_edits':False,'postgres_used':False,'tests_repeated':False,
    'limits':['Static merge/code review only; parent runs actual regression and integration matrix separately']}
out=ROOT/'docs/evidence/year-package-merge-independent-2026-11-04.json';out.parent.mkdir(exist_ok=True,parents=True)
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checked_files':len(checked),'explicit_unions':7,'findings':0,'evidence':str(out.relative_to(ROOT)),'sha256':digest(out.read_bytes())}))

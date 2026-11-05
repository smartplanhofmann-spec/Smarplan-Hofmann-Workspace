import json,os,stat,subprocess,tempfile,tarfile
from pathlib import Path
assert os.geteuid()==0
os.umask(0o022)
results=[]
for name,archive,extra in [('original','/default.tar',[]),('repository_mask','/restricted.tar',[]),('extract_mask','/default.tar',['--no-same-permissions']),('both','/restricted.tar',['--no-same-permissions'])]:
 with tempfile.TemporaryDirectory(prefix='smartplan-git-tar-') as tmp:
  subprocess.run(['tar','-x',*extra,'-f',archive,'-C',tmp],check=True)
  root=Path(tmp)
  modes={str(p.relative_to(root)):format(stat.S_IMODE(p.stat().st_mode),'04o') for p in root.rglob('*')}
  unsafe=[p for p in modes if int(modes[p],8)&0o022]
  assert bool(unsafe)==(name=='original'),(name,modes)
  with tarfile.open(archive) as source:
   executable_mask=source.getmember('deploy/hetzner/online/update-online.sh').mode&0o111
  assert (root/'deploy/hetzner/online/update-online.sh').stat().st_mode&0o111==executable_mask
  assert all(p.stat().st_uid==0 for p in root.rglob('*'))
  results.append({'case':name,'root_uid':os.geteuid(),'process_umask':'0022','modes':modes,'group_or_other_writable':unsafe,'source_executable_mask':format(executable_mask,'03o'),'source_execute_bits_preserved':True})
print(json.dumps(results,indent=2))

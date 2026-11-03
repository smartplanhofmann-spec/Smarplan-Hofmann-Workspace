#!/usr/bin/env bash
# Additive operator entrypoint. Never calls the existing install/update scripts.
set -euo pipefail
umask 0077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
(( EUID == 0 )) || { echo 'Lokaler Root-Betreiber erforderlich.' >&2; exit 1; }
(( $# >= 2 && $# <= 3 )) || { echo 'Aufruf: prepare-company.sh prepare|check|init-owner|start-private MANIFEST [OWNER_EMAIL]' >&2; exit 1; }
smartplan_action=$1
smartplan_manifest=$2
case "$smartplan_action" in prepare|check|init-owner|start-private) ;; *) exit 1 ;; esac
if [[ "$smartplan_action" == init-owner ]]; then (( $# == 3 )) || exit 1; else (( $# == 2 )) || exit 1; fi
# Verify the entire pinned runtime using the protected system interpreter before
# importing any application or virtualenv code with operator privileges.
smartplan_release="$(env -u PYTHONHOME -u PYTHONPATH -u PYTHONSTARTUP -u PYTHONUSERBASE /usr/bin/python3 -I - "$smartplan_manifest" <<'PY'
import json,os,re,stat,sys
from pathlib import Path
def fail():raise SystemExit('Manifest oder kompletter vorbereiteter Release ist nicht geschützt.')
def parents(path):
    if not path.is_absolute():fail()
    for parent in path.parents:
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:fail()
path=Path(sys.argv[1]);parents(path)
with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as source:
    info=os.fstat(source.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1 or info.st_mode&0o022 or not 0<info.st_size<=8192:fail()
    raw=source.read(8193)
def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:fail()
        result[key]=value
    return result
value=json.loads(raw,object_pairs_hook=unique)
slug,commit=value.get('slug'),value.get('source_commit')
if not isinstance(slug,str) or not re.fullmatch('[a-z][a-z0-9]{2,23}',slug) or not isinstance(commit,str) or not re.fullmatch('[a-f0-9]{40}',commit):fail()
root=Path('/opt/smartplan-companies')/slug/'releases'/commit;parents(root)
if root.is_symlink() or not root.is_dir():fail()
count=0
for directory,children,files in os.walk(root,followlinks=False):
    for entry in [Path(directory),*(Path(directory)/name for name in children+files)]:
        count+=1
        if count>200000:fail()
        info=entry.lstat()
        if info.st_uid!=0:fail()
        if stat.S_ISLNK(info.st_mode):
            target=entry.resolve(strict=True);parents(target);info=target.stat()
            if stat.S_ISDIR(info.st_mode) and not target.is_relative_to(root):fail()
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)) or info.st_uid!=0 or info.st_mode&0o022:fail()
if (root/'SOURCE_COMMIT').read_text().strip()!=commit:fail()
if not (root/'app/backend/online/provisioning_host.py').is_file() or not os.access(root/'venv/bin/python',os.X_OK):fail()
print(root)
PY
)"
cd -- "$smartplan_release/app/backend"
smartplan_arguments=("$smartplan_action" --manifest "$smartplan_manifest")
if [[ "$smartplan_action" == init-owner ]]; then smartplan_arguments+=(--owner-email "$3"); fi
exec env -u PYTHONHOME -u PYTHONSTARTUP -u PYTHONUSERBASE -u PGHOSTADDR -u PGSERVICE -u PGSERVICEFILE -u PGOPTIONS -u PGPORT \
  PYTHONPATH="$smartplan_release/app/backend" PYTHONSAFEPATH=1 PYTHONNOUSERSITE=1 \
  "$smartplan_release/venv/bin/python" -m online.provisioning_host "${smartplan_arguments[@]}"

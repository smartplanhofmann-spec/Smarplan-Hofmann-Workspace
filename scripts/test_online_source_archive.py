"""Real Git/tar execution of operator archive boundaries, without running apt or services."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class OnlineArchiveTests(unittest.TestCase):
    def test_both_operator_archives_use_the_frozen_commit_and_include_the_actual_browser(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-operator-archive-')as folder:
            root=Path(folder);repo=root/'source';repo.mkdir()
            def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
            git('init','-q');git('config','user.email','synthetic@example.test');git('config','user.name','Synthetic archive test')
            for name in ('backend/core.py','web/office/index.html','web/office/office.js'):
                p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('original frozen '+name)
            git('add','.');git('commit','-qm','Original synthetic source');commit=git('rev-parse','HEAD')
            (repo/'backend/core.py').write_text('later checkout must not be packaged')
            (repo/'web/office/office.js').write_text('later browser must not be packaged')
            git('add','.');git('commit','-qm','Later synthetic checkout')
            self.assertNotEqual(git('rev-parse','HEAD'),commit)
            for name in ('install-online.sh','update-online.sh'):
                with self.subTest(operator=name):
                    source=(ROOT/'deploy/hetzner/online'/name).read_text()
                    pipeline=re.search(r'git -c tar\.umask=0022[^\n]+\|\n\s*tar[^\n]+',source)
                    self.assertIsNotNone(pipeline)
                    release=root/name;app=release/'app';app.mkdir(parents=True)
                    # Initial install has its established absolute destination;
                    # relocate only that target into the disposable directory.
                    command=pipeline.group().replace('/opt/smartplan-online/app',str(app))
                    environment=dict(os.environ,smartplan_repo=str(repo),smartplan_release=str(release),
                        smartplan_commit=commit,smartplan_install_commit=commit)
                    subprocess.run(['bash','-c','set -euo pipefail\numask 0022\n'+command],env=environment,check=True,capture_output=True,text=True)
                    for asset in ('backend/core.py','web/office/index.html','web/office/office.js'):
                        self.assertTrue((app/asset).is_file(),asset)
                        self.assertEqual((app/asset).read_text(),'original frozen '+asset)
                        self.assertEqual((app/asset).stat().st_mode&0o022,0)


if __name__=='__main__':unittest.main()

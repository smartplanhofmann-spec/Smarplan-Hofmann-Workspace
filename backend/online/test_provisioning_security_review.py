"""Independent local-filesystem regressions for operator provisioning.

No privileged process, service, PostgreSQL, host or external provider is changed.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from online import provisioning
from online.provisioning import Company,write_bundle
from online import provisioning_host
from online.provisioning_host import protected_tree


class ProvisioningFilesystemReview(unittest.TestCase):
    def test_bundle_rejects_private_directory_under_renameable_parent(self):
        company=Company('reviewalpha','a'*32,'reviewalpha.example.test',18761,'b'*40,'c'*32)
        with tempfile.TemporaryDirectory(prefix='synthetic-provision-review-') as temporary:
            root=Path(temporary)
            safe=root/'safe';safe.mkdir(mode=0o700)
            # The control must succeed with the same explicitly injected
            # synthetic trust root. Otherwise mapped / or /tmp ownership
            # could hide the actual writable-parent regression.
            self.assertEqual(write_bundle(safe,company,trusted_root=root)['phase'],'files_prepared')
            parent=root/'untrusted-parent';parent.mkdir(mode=0o700);os.chmod(parent,0o777)
            directory=parent/'operator-reservation';directory.mkdir(mode=0o700)
            # The final directory is private, but another UID may rename it
            # through this non-sticky writable parent. Checking only its mode
            # is insufficient for later path-based root writes.
            with self.assertRaises(ValueError):write_bundle(directory,company,trusted_root=root)
            self.assertEqual(list(directory.iterdir()),[])

    def test_complete_release_checks_transitive_modules_and_dependencies(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-release-review-') as temporary:
            root=Path(temporary)
            paths=(root/'app/backend/core.py',root/'venv/lib/site-packages/dependency/__init__.py')
            for path in paths:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('# synthetic protected module\n')
                path.chmod(0o644)
            protected_tree(root,expected_uid=os.geteuid(),trusted_root=root)
            for path in paths:
                with self.subTest(module=path.relative_to(root)):
                    path.chmod(0o666)
                    with self.assertRaises(ValueError):
                        protected_tree(root,expected_uid=os.geteuid(),trusted_root=root)
                    path.chmod(0o644)
                    protected_tree(root,expected_uid=os.geteuid(),trusted_root=root)

    def test_release_cannot_hide_dependency_directory_outside_verified_tree(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-release-link-review-') as temporary:
            trusted=Path(temporary);root=trusted/'release';root.mkdir(mode=0o700)
            dependency=root/'dependency';dependency.mkdir(mode=0o755)
            (dependency/'__init__.py').write_text('# synthetic protected dependency\n')
            (root/'internal').symlink_to(dependency,target_is_directory=True)
            protected_tree(root,expected_uid=os.geteuid(),trusted_root=trusted)
            outside=trusted/'not-in-release';outside.mkdir(mode=0o755)
            (root/'external').symlink_to(outside,target_is_directory=True)
            original_guard=provisioning._safe_parents
            def fixture_guard(path,*,uid,trusted_root=None):
                # Check actual parent permissions up to the same synthetic
                # root, so mapped host-root ownership cannot mask the separate
                # rule against a directory outside the verified release.
                return original_guard(path,uid=uid,trusted_root=trusted_root or trusted)
            with patch.object(provisioning,'_safe_parents',side_effect=fixture_guard):
                with self.assertRaisesRegex(ValueError,'Externe Verzeichnislinks'):
                    protected_tree(root,expected_uid=os.geteuid(),trusted_root=trusted)

    def test_real_loopback_listener_must_belong_to_reported_own_process(self):
        # The container has no systemd. Only its status/PID response is mocked;
        # the socket, separate process, /proc descriptors and inode are real.
        source="""import socket,sys
with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
    listener.bind(('127.0.0.1',0));listener.listen(1)
    print(listener.getsockname()[1],flush=True)
    sys.stdin.buffer.read(1)
"""
        child=subprocess.Popen([sys.executable,'-u','-c',source],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env={'PATH':os.defpath,'LANG':'C.UTF-8','PYTHONNOUSERSITE':'1'})
        try:
            port=int(child.stdout.readline())
            def status(command,**kwargs):
                return b'active\n' if '--property=ActiveState' in command else str(child.pid).encode()
            with patch.object(provisioning_host,'_run',side_effect=status):
                provisioning_host.verify_listener('synthetic-review-api.service',port)
            def wrong_process(command,**kwargs):
                return b'active\n' if '--property=ActiveState' in command else str(os.getpid()).encode()
            # The listener still exists and appears in the namespace TCP list;
            # this alleged service PID does not own that socket descriptor.
            with patch.object(provisioning_host,'_run',side_effect=wrong_process):
                with self.assertRaisesRegex(ValueError,'gehört nicht zur eigenen API-Unit'):
                    provisioning_host.verify_listener('synthetic-review-api.service',port)
        finally:
            child.communicate(input=b'x',timeout=10)


if __name__=='__main__':unittest.main()

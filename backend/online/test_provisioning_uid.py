"""Actual different Linux UIDs inside an isolated disposable local container.

No host mounts, networking, persistent volumes or host account changes. This
checks private file boundaries; it does not certify a production systemd host.
"""
import os
import subprocess
import unittest
import uuid


@unittest.skipUnless(os.environ.get('SMARTPLAN_UID_CONTAINER_TEST')=='1','Explicit disposable container UID acceptance required')
class CompanyUidIsolation(unittest.TestCase):
    def test_two_runtime_uids_cannot_read_write_or_replace_foreign_private_files(self):
        environment={key:value for key,value in os.environ.items() if key not in (
            'DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH')}
        prefix=['docker','--host=unix:///var/run/docker.sock']
        def run(*args,check=True):
            result=subprocess.run([*prefix,*args],env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            if check:self.assertEqual(result.returncode,0,'Local disposable container operation failed')
            return result
        name='smartplan-company-uids-'+uuid.uuid4().hex[:12]
        run('run','--detach','--name',name,'--network','none','--read-only',
            '--security-opt','no-new-privileges','--cap-drop','ALL','--cap-add','CHOWN',
            '--cap-add','DAC_OVERRIDE','--cap-add','FOWNER','--tmpfs','/proof:rw,nosuid,nodev,noexec,size=1m',
            '--entrypoint','sleep','postgres:16','180')
        try:
            run('exec','--user','0:0',name,'sh','-eu','-c',
                'mkdir -m 700 /proof/alpha /proof/beta; '
                'printf synthetic-alpha > /proof/alpha/vault; printf synthetic-beta > /proof/beta/vault; '
                'chmod 600 /proof/alpha/vault /proof/beta/vault; '
                'chown -R 24001:24001 /proof/alpha; chown -R 24002:24002 /proof/beta')
            for uid,own,other in (('24001:24001','alpha','beta'),('24002:24002','beta','alpha')):
                run('exec','--user',uid,name,'sh','-eu','-c',
                    'cat /proof/'+own+'/vault >/dev/null; printf own-write > /proof/'+own+'/new')
                for command in ('cat /proof/'+other+'/vault >/dev/null',
                                'printf foreign > /proof/'+other+'/new',
                                'rm /proof/'+other+'/vault',
                                'mv /proof/'+other+' /proof/stolen'):
                    self.assertNotEqual(run('exec','--user',uid,name,'sh','-c',command,check=False).returncode,0)
            run('exec','--user','0:0',name,'sh','-eu','-c',
                'test "$(cat /proof/alpha/vault)" = synthetic-alpha; '
                'test "$(cat /proof/beta/vault)" = synthetic-beta')
        finally:run('rm','--force',name)


if __name__=='__main__':unittest.main()

"""Deterministic CycloneDX source-lock inventory; no network or installed-code scan.

Release binaries, OS packages, JDK/validators, Flutter engine and remote services
need their own release evidence. Absence of advisories is never inferred here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LOCKS = ('backend/requirements.lock', 'backend/online/requirements.lock', 'backend/plan_import/requirements.lock',
         'app/pubspec.lock', 'web/office/package-lock.json')


def python_packages(source):
    result = []
    for line in source.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)', line)
        if not match:
            raise ValueError('Only explicitly pinned Python packages are inventoried: ' + line[:100])
        name, version = match.groups()
        result.append(dict(name=re.sub(r'[-_.]+', '-', name).lower(), version=version))
    return result


def dart_packages(source):
    result = []
    blocks = re.findall(r'^  ([A-Za-z0-9_]+):\n((?: {4}[^\n]*\n|\n)+)', source, re.M)
    for name, block in blocks:
        def field(key):
            match = re.search(r'^\s+' + key + r':\s*[\"\']?([^\n\"\']+)', block, re.M)
            return match.group(1).strip() if match else None
        kind, version = field('source'), field('version')
        if kind == 'sdk':
            continue  # SDK pseudo-versions are not the installed Flutter engine.
        if kind != 'hosted' or not version or not re.fullmatch(r'[a-f0-9]{64}', field('sha256') or ''):
            raise ValueError('Unverified or unsupported Dart lock source: ' + name)
        result.append(dict(name=name, version=version, sha256=field('sha256'),
                           dependency=field('dependency')))
    if not result:
        raise ValueError('No hosted Dart packages found in lockfile')
    return result


def inventory(root=ROOT):
    components, locks = {}, []
    def add(ecosystem, item, source, *, dev=False):
        purl = 'pkg:' + ecosystem + '/' + quote(item['name'], safe='/') + '@' + quote(item['version'], safe='.+-')
        value = components.setdefault(purl, dict(type='library', name=item['name'], version=item['version'],
            purl=purl, **{'bom-ref': purl}, properties=[]))
        value['properties'].append(dict(name='smartplan:lockfile', value=source))
        value['properties'].append(dict(name='smartplan:use:' + source, value='development' if dev else 'application'))
        if item.get('sha256'):
            value['hashes'] = [dict(alg='SHA-256', content=item['sha256'])]
        if item.get('license'):
            value['licenses'] = [dict(license=dict(name=item['license']))]
    for filename in LOCKS:
        raw = (root / filename).read_bytes()
        locks.append(dict(path=filename, sha256=hashlib.sha256(raw).hexdigest()))
        if filename.endswith('requirements.lock'):
            for item in python_packages(raw.decode()): add('pypi', item, filename)
        elif filename.endswith('pubspec.lock'):
            for item in dart_packages(raw.decode()): add('pub', item, filename, dev=item['dependency'] == 'direct dev')
        else:
            data = json.loads(raw)
            if data.get('lockfileVersion') != 3 or not isinstance(data.get('packages'), dict):
                raise ValueError('Unsupported npm lock format')
            for path, entry in data['packages'].items():
                if not path: continue
                if 'node_modules/' not in path or not entry.get('version') or entry.get('link'):
                    raise ValueError('Unsupported npm package source')
                name = entry.get('name') or path.rsplit('node_modules/', 1)[1]
                add('npm', dict(name=name, version=entry['version'], license=entry.get('license')), filename, dev=entry.get('dev', False))
    return dict(bomFormat='CycloneDX', specVersion='1.6', version=1,
        metadata=dict(component=dict(type='application', name='Smartplan CRM ERP source'), properties=[
            dict(name='smartplan:scope', value='source_lock_inventory'),
            dict(name='smartplan:locks', value=json.dumps(locks, sort_keys=True, separators=(',', ':'))),
            dict(name='smartplan:advisory_scan', value='not_performed_by_this_script'),
            dict(name='smartplan:release_gaps', value='OS packages; Flutter engine/SDK; bundled native DLLs; JDK and invoice validators; remote providers; binary provenance'),
            dict(name='smartplan:license_status', value='npm declared licenses only; other redistribution licenses require separate verification')]),
        components=[components[key] for key in sorted(components)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--root', default=ROOT, type=Path)
    args = parser.parse_args()
    value = inventory(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print(str(len(value['components'])) + ' pinned components inventoried; no vulnerability or release approval implied.')


if __name__ == '__main__': main()

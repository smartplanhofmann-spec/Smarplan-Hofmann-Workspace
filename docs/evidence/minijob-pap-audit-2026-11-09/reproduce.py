"""Re-run the audit's synthetic inputs against pinned XML, never application tax code."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', required=True, type=Path)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    evidence = json.loads((folder / 'xml-reference.json').read_text())
    root = folder.parents[2]
    generator = root / evidence['generator_path']
    if hashlib.sha256(generator.read_bytes()).hexdigest() != evidence['generator_sha256']:
        raise ValueError('Independent generator does not match the observed source.')
    spec = importlib.util.spec_from_file_location('independent_pap_reference', generator)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    source = reference.java_source(args.xml.read_bytes())
    if hashlib.sha256(source.encode()).hexdigest() != evidence['generated_java_sha256']:
        raise ValueError('Generated Java does not match the observed source.')
    observed = reference.oracle(source, [case['input'] for case in evidence['cases']])
    expected = [case['xml_output'] for case in evidence['cases']]
    if observed != expected:
        raise AssertionError('Observed PAP outputs changed.')
    print(json.dumps({'cases': len(observed), 'identical': True, 'production_code_loaded': False}))


if __name__ == '__main__':
    main()

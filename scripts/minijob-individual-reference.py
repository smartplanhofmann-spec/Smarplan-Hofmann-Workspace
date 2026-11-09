"""Generate independent full-month minijob vectors from the pinned BMF XML.

Only the existing Java/XML translator is imported; no application payroll
kernel participates in generating the expected values.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    audit = json.loads((root / 'docs/evidence/minijob-pap-audit-2026-11-09/xml-reference.json').read_text())
    raw = args.xml.read_bytes()
    if hashlib.sha256(raw).hexdigest() != audit['xml_sha256']:
        raise ValueError('Unexpected XML original')
    generator = root / audit['generator_path']
    if hashlib.sha256(generator.read_bytes()).hexdigest() != audit['generator_sha256']:
        raise ValueError('Unexpected independent generator')
    spec = importlib.util.spec_from_file_location('minijob_xml_reference', generator)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    java = module.java_source(raw)
    if hashlib.sha256(java.encode()).hexdigest() != audit['generated_java_sha256']:
        raise ValueError('Unexpected generated Java')
    inputs = []
    for tax_class in (1, 5):
        for krv in (0, 1):
            for gross in (17500, 17501, 20000, 33333, 49999, 50000, 50001, 60299, 60300):
                values = deepcopy(audit['cases'][0]['input'])
                values.update(STKL=tax_class, KRV=krv, RE4=gross)
                inputs.append(values)
    observed = module.oracle(java, inputs)
    result = dict(schema_version=1, xml_sha256=audit['xml_sha256'],
                  xml_origin=audit['xml_origin'], generator_path=audit['generator_path'],
                  generator_sha256=audit['generator_sha256'], generated_java_sha256=audit['generated_java_sha256'],
                  production_code_loaded=False,
                  cases=[dict(id=f'class{values["STKL"]}_krv{values["KRV"]}_gross{values["RE4"]}',
                              input=values, xml_output=output)
                         for values, output in zip(inputs, observed)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(cases=len(observed), production_code_loaded=False,
                          output_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()

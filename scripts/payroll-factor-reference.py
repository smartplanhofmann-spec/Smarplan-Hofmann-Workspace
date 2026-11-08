"""Reproduce synthetic factor vectors with the pinned PAP XML, without our kernel.

Developer-only, offline runner. Supply the separately obtained XML explicitly;
its exact digest is mandatory before any Java is generated or executed. Java's
source-file launcher runs the unchanged XML decimal expressions. Production
does not import this script, execute Java, or download employee tax data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import tempfile
from xml.etree import ElementTree as ET

XML_SHA256 = '63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4'
XML_MIRROR = ('https://raw.githubusercontent.com/manuelbusch/paprun/'
              'cdf564daec7f617d54181eb8b14232e48a59dd7a/tests/data/Lohnsteuer2026.xml')
OFFICIAL_XML = 'https://www.bmf-steuerrechner.de/javax.faces.resource/daten/xmls/Lohnsteuer2026.xml.xhtml'


def java_source(raw):
    if hashlib.sha256(raw).hexdigest() != XML_SHA256:
        raise ValueError('PAP XML digest mismatch; no generated source is executed.')
    root = ET.fromstring(raw)
    declarations = [f'public {v.attrib["type"]} {v.attrib["name"]} = {v.attrib.get("default", "0")};'
                    for group in root.find('VARIABLES') for v in group]
    declarations += [f'public final {v.attrib["type"]} {v.attrib["name"]} = {v.attrib["value"]};'
                     for v in root.find('CONSTANTS')]

    def statements(nodes):
        result = []
        for n in nodes:
            if n.tag == 'EVAL':
                result.append(n.attrib['exec'] + ';')
            elif n.tag == 'EXECUTE':
                result.append(n.attrib['method'] + '();')
            elif n.tag == 'IF':
                result.append('if (' + n.attrib['expr'] + ') {')
                result.extend(statements(n.find('THEN')))
                if n.find('ELSE') is not None:
                    result.append('} else {')
                    result.extend(statements(n.find('ELSE')))
                result.append('}')
            else:
                raise ValueError('Unexpected PAP instruction: ' + n.tag)
        return result

    methods = []
    for method in root.find('METHODS'):
        name = 'runPAP' if method.tag == 'MAIN' else method.attrib['name']
        methods += [f'void {name}() {{', *statements(method), '}']
    outputs = [v.attrib['name'] for group in root.find('VARIABLES')
               if group.tag == 'OUTPUTS' for v in group]
    printer = [f'out.add("\\\"{key}\\\":" + p.{key}.toPlainString());' for key in outputs]
    return '\n'.join([
        'import java.math.BigDecimal;', 'import java.io.*;', 'import java.util.*;',
        'class PAPOracle {', *declarations, *methods,
        'public static void main(String[] args) throws Exception {',
        'var reader = new BufferedReader(new InputStreamReader(System.in));',
        'for (String line; (line = reader.readLine()) != null;) {',
        'var p = new PAPOracle();',
        'for (String item : line.split(" ")) {',
        'String[] pair = item.split("=", 2);',
        'var field = PAPOracle.class.getField(pair[0]);',
        'if (field.getType() == int.class) field.setInt(p, Integer.parseInt(pair[1]));',
        'else if (field.getType() == double.class) field.setDouble(p, Double.parseDouble(pair[1]));',
        'else field.set(p, new BigDecimal(pair[1]));', '}',
        'p.runPAP();', 'var out = new StringJoiner(",", "{", "}");',
        *printer, 'System.out.println(out);', '}', '}', '}',
    ])


def pap_inputs(case):
    p = case
    return dict(af=1, f=p['factor'], LZZ=p['period'], RE4=p['gross_minor'],
                STKL=4, ZKF=str(p['children_half_units'] / 2),
                KVZ=p['additional_health_percent'], PVS=int(p['saxony']),
                PVZ=int(p['childless_surcharge']), PVA=p['care_child_discounts'],
                R=int(p['church_member']))


def cases():
    base = dict(gross_minor=500000, period=2, tax_class=4, factor='0.753',
                children_half_units=0, additional_health_percent='2.90',
                saxony=False, childless_surcharge=True, care_child_discounts=0,
                church_member=False, allowance_minor=0, addition_minor=0)
    result = []
    for period in (1, 2):
        for gross in (0, 1, 175000, 500001, 850000, 1500000):
            for factor in ('0.000', '0.001', '0.753', '0.999'):
                result.append(dict(base, period=period, gross_minor=gross, factor=factor))
    rng = random.Random(20261108)
    for _ in range(120):
        discount = rng.randrange(5)
        result.append(dict(base, period=rng.choice((1, 2)),
            gross_minor=rng.randrange(1, 60000001),
            factor=f'0.{rng.randrange(1000):03d}',
            children_half_units=rng.choice((0, 1, 2, 3, 4, 8, 20)),
            additional_health_percent=rng.choice(('0', '2.90', '3.29', '20')),
            saxony=bool(rng.randrange(2)), childless_surcharge=not discount,
            care_child_discounts=discount, church_member=bool(rng.randrange(2))))
    for period in (1, 2):
        result.append(dict(base, period=period, gross_minor=10**12 // (12 if period == 2 else 1),
                           church_member=True, factor='0.999'))
    return result


def oracle(source, rows):
    with tempfile.TemporaryDirectory(prefix='smartplan-factor-oracle-') as directory:
        java = Path(directory) / 'PAPOracle.java'
        java.write_text(source, encoding='utf-8')
        completed = subprocess.run(['java', str(java)], text=True, check=True,
            input=''.join(' '.join(f'{k}={v}' for k, v in row.items()) + '\n' for row in rows),
            capture_output=True, timeout=90)
    values = [json.loads(line) for line in completed.stdout.splitlines()]
    if len(values) != len(rows):
        raise ValueError('PAP result count mismatch.')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    inputs = cases()
    expected = oracle(java_source(options.xml.read_bytes()), [pap_inputs(c) for c in inputs])
    proof = dict(schema_version=1, reference='pinned_2026_xml_java_decimal_expressions',
        xml_sha256=XML_SHA256, official_xml_url=OFFICIAL_XML, reviewed_mirror_url=XML_MIRROR,
        direct_official_xml_download=False, official_software_approval=False,
        cases=[dict(inputs=i, expected={k: e[k] for k in ('LSTLZZ', 'SOLZLZZ', 'BK')})
               for i, e in zip(inputs, expected)])
    options.output.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(cases=len(inputs), xml_sha256=XML_SHA256, output=str(options.output))))


if __name__ == '__main__':
    main()

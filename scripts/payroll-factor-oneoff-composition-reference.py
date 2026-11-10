"""Independent XML tax outputs for actual synthetic V15 source compositions."""
import argparse
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('oracle',Path(__file__).with_name('payroll-factor-reference.py'))
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--xml',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    base=dict(af=1,f='0.753',LZZ=2,RE4=419355,JRE4=13419355,SONSTB=50000,STKL=4,ZKF='0',KVZ='2.90',PVS=0,PVZ=1,PVA=0,R=0)
    rows=[dict(base,JRE4=annual,f=factor,R=church) for annual in (1419355,13419355) for factor in ('0.000','0.753','0.999') for church in (0,1)]
    outputs=oracle.oracle(oracle.java_source(args.xml.read_bytes()),rows)
    proof=dict(schema_version=1,xml_sha256=oracle.XML_SHA256,production_kernel_imported=False,runtime_network=False,official_system_approval=False,
        cases=[dict(pap_input=row,expected={key:int(value[key]) for key in ('STS','SOLZS','BKS')}) for row,value in zip(rows,outputs)])
    args.output.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(dict(cases=len(rows),production_kernel_imported=False,xml_sha256=oracle.XML_SHA256)))


if __name__=='__main__':main()

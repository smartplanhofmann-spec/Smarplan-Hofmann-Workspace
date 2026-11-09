#!/usr/bin/env python3
"""Generate untouched real stock return records; no calculated DTO stand-ins."""
import argparse
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from test_material_return_fixture import MaterialReturnFixture


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'app/test/fixtures/material_return.json')
    args=parser.parse_args()
    owner=unittest.TestCase('runTest')
    try:
        result=dict(schema_version=1,synthetic=True,
            main=MaterialReturnFixture(owner).main(),rounding=MaterialReturnFixture(owner).rounding())
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        print(args.output)
    finally:owner.doCleanups()


if __name__=='__main__':main()

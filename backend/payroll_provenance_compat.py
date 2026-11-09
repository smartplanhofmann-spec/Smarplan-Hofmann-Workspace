"""Exact historical v8 metadata reproduction across LF/CRLF source bundles.

Only the two provenance fields may differ from the actual recalculation.
Each accepted pair is derived from the currently trusted, unchanged kernels
under a finite set of line-ending encodings. No archived value, file, money
amount, source, rule or PDF is rewritten. No global rule mutation or worker IO.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from payroll_factor_2026 import FACTOR_RULE_VERSION, FACTOR_RULES
from payroll_pap_factor_2026 import FACTOR_PAP_PROVENANCE
import payroll_pap_2026 as annual
import payroll_pap_factor_2026 as factor


def _sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':')).encode()).hexdigest()


def _source_encodings(path):
    lf=Path(path).read_bytes().replace(b'\r\n',b'\n')
    return tuple(hashlib.sha256(raw).hexdigest() for raw in (lf,lf.replace(b'\n',b'\r\n')))


@lru_cache(maxsize=1)
def _trusted_v8_metadata_pairs():
    pairs=set()
    for annual_sha in _source_encodings(annual.__file__):
        for factor_sha in _source_encodings(factor.__file__):
            provenance=dict(FACTOR_PAP_PROVENANCE,
                annual_primitive_sha256=annual_sha,module_sha256=factor_sha)
            pap_sha=_sha(provenance)
            pairs.add((_sha(dict(FACTOR_RULES,pap_provenance_sha256=pap_sha)),pap_sha))
    return frozenset(pairs)


def matches_factor_monthly(calculated,original):
    """Match all original values exactly, including one trusted metadata pair."""
    if (not isinstance(calculated,dict) or not isinstance(original,dict)
            or calculated.get('rule_version')!=FACTOR_RULE_VERSION
            or original.get('rule_version')!=FACTOR_RULE_VERSION
            or calculated.get('scope')!='regular_standard_factor_monthly'
            or calculated.get('payroll_calculation_complete') is not True):
        return False
    for rules_sha,pap_sha in _trusted_v8_metadata_pairs():
        candidate=dict(calculated,rules_sha256=rules_sha,pap_provenance_sha256=pap_sha)
        if candidate==original:
            return True
    return False
